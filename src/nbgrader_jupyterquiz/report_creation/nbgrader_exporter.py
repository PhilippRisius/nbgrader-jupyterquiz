"""
nbgrader plugin for exporting graded assignments in various formats.

CSVExporter -- generate csv table
MailExporter -- send feedback mails
ReportCardExporter -- generate PDF report card
FlexNowExporter -- add overall results to FlexNow csv table
TableExporter -- generate PDF report for all students
"""

import datetime
import itertools
import json
import logging
import os
import pathlib
import smtplib

import nbgrader.api
import numpy as np
import pandas as pd
import pypandoc
from nbgrader.plugins import ExportPlugin


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def confirm(prompt, log=logger):
    valid = {
        "yes": True,
        "y": True,
        "no": False,
        "n": False,
        "abort": None,
        "a": None,
    }
    while (response := input(prompt)) not in valid:
        log.warning('Please respond with "yes", "no", or "abort" [y/n/a].')
    return valid[response]


def parse_templates(templates, log=logger):
    parsed_templates = {}
    template_path = pathlib.Path(templates.get("path"))
    if template_path.is_dir():
        with pathlib.Path(template_path / templates.get("header")).open() as f:
            parsed_templates["subject"] = f.readline().removeprefix("subject: ").removesuffix("\n")
            parsed_templates["header"] = f.read()
        with pathlib.Path(template_path / templates.get("footer")).open() as f:
            parsed_templates["footer"] = f.read()
        logger.info(
            f'Exporting feedback with subject: \n"{parsed_templates["subject"]}"\n'
            f'and message template: """\n{parsed_templates["header"]}\n{parsed_templates["footer"]}"""'
        )
        for key, value in templates.get("additional").items():
            parsed_templates[key] = {}
            for k, v in value.items():
                with pathlib.Path(template_path / key / v).open() as f:
                    parsed_templates[key][k] = f.read()
        return parsed_templates
    else:
        log.error(f'Mail templates not found in directory "{template_path.resolve()}"')
        exit(1)


def read_config(filename, log=logger, **kwargs):
    with pathlib.Path(filename).open() as config_file:
        config = json.load(config_file)

    # read mail templates
    if "message_templates" in config:
        config["message_templates"] = parse_templates(config["message_templates"])
    else:
        log.warning("No message templates found in config file.")

    # load mail data
    if "mail_data" in config:
        address_book_path = pathlib.Path(config["mail_data"].get("address_book"))
        if address_book_path.is_file():
            log.info('Loading address book from file "%s"', address_book_path)
            with pathlib.Path(address_book_path).open() as f:
                address_book = json.load(f)
            config["mail_data"]["address_book"] = address_book
        else:
            log.warning('Address book not found in file "%s', address_book_path)
            address_book = {}
        sender = config["mail_data"].get("sender")

        ready_to_send = False
        while not ready_to_send:
            if sender in address_book:
                ready_to_send = confirm(f"Sending mails as {sender}. Is this correct [y/n/a]?")
                if ready_to_send is None:
                    exit(1)
            if not ready_to_send:
                if sender not in address_book:
                    log.warning('Sender "%s" not found in address book!', sender)
                log.info("Please provide sender from address book keys")
                sender = input(f"Choose from {tuple(address_book.keys())}\n> ")
        config["mail_data"]["smtp"] |= address_book[sender]
        config["mail_data"]["sender"] = config["mail_data"]["smtp"].pop("name")
    else:
        log.warning("No data for sending mails given.")

    # set feedback location
    if "feedback" in config:
        if config["feedback"].get("attach"):
            path = None
            location = config["feedback"].get("location")
            if location:
                path = pathlib.Path(location)
                if not path.exists():
                    log.warning(f"Feedback location does not exist: {path.resolve()}")
                    location = None
            config["feedback"]["location"] = location
            log.info(f"Finding feedback files {'in {path}' if path else 'via nbgrader'}")

            if not config["feedback"].get("suffix"):
                log.warning("Feedback suffix not given. Assume html.")
                config["feedback"]["suffix"] = ".html"
            if not config["feedback"].get("missing_ok"):
                log.warning("Feedback attachment if no files found unclear. Assume it is ok to send.")
                config["feedback"]["missing_ok"] = True
        else:
            log.info("Not attaching feedback")
    else:
        log.warning("No config for feedback files found. Not attaching any.")
        config["feedback"]["attach"] = False

    # read report card templates
    if (report_cards := config.get("report_cards")) is not None:
        report_cards["location"] = pathlib.Path(report_cards["location"])
        with pathlib.Path(report_cards["location"] / report_cards["template"]).open() as f:
            report_cards["template"] = f.read()
        config["report_cards"] = report_cards
    else:
        log.warning("No report card information found in config file.")

    # parse grading information
    if config.get("grading") is None:
        log.info("No grading information given. Admitting everyone.")
        config["grading"] = {"default_admission": True}
    else:
        log.info("Students need {points_needed} of {points_100_percent} points to pass.".format_map(config["grading"]))
        if (percentage_table := config["grading"].get("percentage_to_grade")) is not None:

            def percentage_to_grade(percentage):
                return max(
                    filter(
                        lambda entry: percentage >= float(entry[0]),
                        percentage_table.items(),
                    )
                )[1]

            config["grading"]["percentage_to_grade"] = percentage_to_grade

    # prepare appointments
    if config.get("appointments"):
        log.info(f"Distributing students to appointments {config['appointments']}.")
        for key, value in config["appointments"].items():
            if isinstance(value, list):
                config["appointments"][key] = (
                    itertools.cycle(value),
                    {date: [] for date, loc in value},
                )

    return config


def find_grade(grade_book, cell, notebook, assignment, student):
    try:
        return grade_book.find_grade(cell.name, notebook.name, assignment.name, student.id).score
    except nbgrader.api.MissingEntry:
        return pd.NA


def has_entry(gradebook, assignment, missing_ok, student=None, notebook=None):
    if missing_ok:
        return True
    if student:
        if notebook:
            return notebook.name in [notebook.name for notebook in gradebook.find_submission(assignment.name, student.id).notebooks]
        else:
            return assignment.name in [assignment.name for assignment in gradebook.student_submissions(student.id)]
    else:
        return gradebook.assignment_submissions(assignment.name)


def export_to_multiindex(gradebook, students, assignments, missing_ok):
    """Export the grades as a 2D table for printing or uploading"""
    grades_dict = {
        student.id: {
            (assignment.name, notebook.name, cell_index): find_grade(gradebook, cell, notebook, assignment, student)
            for assignment in assignments
            if has_entry(gradebook, assignment, missing_ok, student)
            for notebook in assignment.notebooks
            if has_entry(gradebook, assignment, student, notebook)
            for cell_index, cell in enumerate(itertools.chain(notebook.grade_cells, notebook.task_cells))
        }
        for student in students
    }

    grades_dict["reachable"] = {
        (assignment.name, notebook.name, cell_index): cell.max_score
        for assignment in assignments
        for notebook in assignment.notebooks
        for cell_index, cell in enumerate(itertools.chain(notebook.grade_cells, notebook.task_cells))
    }

    grades_table = pd.DataFrame.from_dict(grades_dict).fillna(np.nan)
    grades_table.index = pd.MultiIndex.from_tuples(grades_table.index, names=("Assignment", "Task", "Cell"))
    return grades_table


def format_details(results, reachable):
    if results.fillna(0.0).apply(float.is_integer).all():
        results = results.astype("Int64")  # use nullable integer value
    details = (results.astype(str) + "/" + reachable.astype(str)).unstack(fill_value="")
    details.columns.name = ""
    details.columns = "Teil " + (details.columns + 1).astype(str)
    details.index.names = ["Übung", "Aufgabe"]
    return details


def find_attachments(feedback_files: str, student_id, assignments):
    feedback_paths = {
        pathlib.Path(
            feedback_files.format(
                nbgrader_step="feedback",
                student_id=student_id,
                assignment_id=assignment.name,
                notebook_name=notebook.name,
            )
        ).resolve()
        for assignment in assignments
        for notebook in assignment.notebooks
    }
    attachments = list(filter(pathlib.Path.is_file, feedback_paths))
    return attachments


def send_mail(message, smtp, to_addrs, log=logger):
    sent = True
    while sent := (sent or confirm("Retry sending mail ([y]es / [n]o / [a]bort)? ")):
        try:
            smtp.conn.sendmail(
                from_addr=smtp.sender_email,
                to_addrs=to_addrs,
                msg=message,
            )
            return True
        except smtplib.SMTPException as e:
            sent = False
            log.warning("Could not send mail: %s.", e)
    else:
        return sent


class CSVExporter(ExportPlugin):
    """
    Export grades to a csv file.

    missing_ok -- whether to include rows with missing data
    aggregated -- whether to aggregate to task level
    """

    # TODO: use `read_config`
    missing_ok: bool
    aggregated: bool

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.to: str = str(self.to) or "grades.csv"

    def export(self, gradebook):
        students = list(map(gradebook.find_student, self.student)) or gradebook.students

        assignments = list(map(gradebook.find_assignment, self.assignment)) or gradebook.assignments

        grades_table = export_to_multiindex(
            gradebook,
            students,
            assignments,
            self.missing_ok,
        )

        self.log.info(f"exporting to {self.to}")

        indices = [
            ".".join(map(str, (task_index + 1, subtask_index + 1, cell_index + 1)))
            for task_index, task in enumerate(grades_table.index.levels[0])
            for subtask_index, subtask in enumerate(grades_table.loc[(task, ...)].index.remove_unused_levels().levels[0])
            for cell_index, cell in enumerate(grades_table.loc[(task, subtask)].index)
        ]

        grades_table.index = pd.Index(indices, name="Kennung")

        grades_table.T.to_csv(pathlib.Path(self.to).resolve(), header=True, index_label="Kennung")


class DetailedCompleteExporter(CSVExporter):
    missing_ok = True
    aggregated = False


class DetailedSparseExporter(CSVExporter):
    missing_ok = False
    aggregated = False


class AggregateExporter(CSVExporter):
    missing_ok = True
    aggregated = True


class ReportCardExporter(ExportPlugin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.export_config = read_config(self.config["ExportPlugin"].get("config"))

    def export(self, gradebook):
        students = list(map(gradebook.find_student, self.student)) or gradebook.students

        assignments = list(map(gradebook.find_assignment, self.assignment)) or gradebook.assignments

        grades_table = (
            export_to_multiindex(
                gradebook,
                students,
                assignments,
                missing_ok=self.export_config["feedback"].get("missing_ok"),
            )
            .round(2)
            .sample(axis=1, frac=1.0, random_state=6)
        )

        reachable = grades_table["reachable"]
        if reachable.apply(float.is_integer).all():
            reachable = reachable.astype(int)

        format_assignment = self.export_config["module"] | {
            "module_name": os.getenv("COURSE_TITLE"),
            "assignment_id": '", "'.join(str(a.name) for a in assignments),
            "points_max": reachable.sum(),
            "points_100_percent": self.export_config["grading"].get("points_100_percent"),
            "date": datetime.datetime.date(datetime.datetime.today()),
        }
        if isinstance(format_assignment["lecturer_address"], list):
            format_assignment["lecturer_address"] = '"\n-  "'.join(format_assignment["lecturer_address"])

        for student_id, results in grades_table.items():
            if student_id == "reachable":
                continue

            student = gradebook.find_student(str(student_id))
            details = format_details(results, reachable)

            points_reached = results.sum()
            percentage_reached = points_reached * 100 / self.export_config["grading"].get("points_100_percent")
            grade = self.export_config["grading"]["percentage_to_grade"](percentage_reached)
            if points_reached < self.export_config["grading"].get("points_needed", 0):
                self.log.warning(f"Student {student.first_name} {student.last_name} has not passed. Not creating report card.")
                continue

            format_student = {
                "first_name": student.first_name,
                "last_name": student.last_name,
                "points_reached": points_reached,
                "grade": grade,
                "details": details.to_string(),
            }

            report_card = self.export_config["report_cards"]["template"].format(**format_assignment, **format_student)

            report_file = str(
                (self.export_config["report_cards"]["location"] / f"{student_id}_{student.first_name}_{student.last_name}.pdf").resolve()
            )

            logger.info("Converting markdown to pdf with pandoc")
            pypandoc.convert_text(
                report_card,
                "pdf",
                format="md",
                outputfile=report_file,
                extra_args=self.export_config["report_cards"].get("pandoc-args", []),
            )


class FlexNowExporter(ExportPlugin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.export_config = read_config(self.config["ExportPlugin"].get("config"))

    def export(self, gradebook):
        students = list(map(gradebook.find_student, self.student)) or gradebook.students

        assignments = list(map(gradebook.find_assignment, self.assignment)) or gradebook.assignments

        grades_table = export_to_multiindex(
            gradebook,
            students,
            assignments,
            missing_ok=self.export_config["feedback"].get("missing_ok"),
        )

        points_100_percent = self.export_config["grading"]["points_100_percent"]
        percentages = (
            pd.DataFrame(
                {
                    "participated": grades_table.notna().any(),
                    "percentage": grades_table.sum(axis=0) * 100 / points_100_percent,
                }
            )
            .drop("reachable")
            .reset_index(names="student_id")
        )

        grades_table = (
            percentages.assign(student=percentages["student_id"].apply(lambda student_id: gradebook.find_student(student_id)))
            .assign(
                first_name=lambda df: df.student.apply(lambda s: s.first_name),
                last_name=lambda df: df.student.apply(lambda s: s.last_name),
                email=lambda df: df.student.apply(lambda s: s.email),
                grade=lambda df: df.percentage.apply(self.export_config["grading"]["percentage_to_grade"]),
            )
            .drop(columns=["student_id", "student"])
            .set_index(["last_name", "first_name", "email"])
        )

        flexnow_format = self.export_config["flexnow"].get("csv_format", {})
        flexnow_dir = pathlib.Path(self.export_config["flexnow"]["location"])
        for flexnow_file in flexnow_dir.glob(self.export_config["flexnow"]["glob"]):
            flexnow_table = pd.read_csv(flexnow_file, **flexnow_format).join(
                grades_table,
                on=["Nachname", "Vorname", "Email"],
                rsuffix="_nbgrader",
            )
            flexnow_table = flexnow_table.assign(Note=flexnow_table.loc[:, ["Note", "grade"]].max(axis=1))

            (
                flexnow_table.assign(
                    Bemerkung=(
                        flexnow_table["Bemerkung"].reset_index(drop=True)
                        + flexnow_table["participated"].map(
                            {
                                True: ", teilgenommen",
                                False: ", nicht teilgenommen",
                                np.nan: "",
                            }
                        )
                        + flexnow_table["Note"]
                        .isna()
                        .map(
                            {
                                True: ", Prüfungsvorleistung nicht erreicht",
                                False: "",
                            }
                        )
                    )
                ).drop(columns=["grade", "percentage", "participated"])
            ).to_csv(flexnow_file.with_suffix(".csv"), **flexnow_format)


class TableExporter(ExportPlugin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.export_config = read_config(self.config["ExportPlugin"].get("config"))

    def export(self, gradebook):
        raise NotImplementedError("PDF Table export is not yet implemented.")
        # TODO: Implement functionality from `nbgrader_jupyterquiz.create_report`


class SMTPConnection:
    def __init__(self, server=None, port=None, username=None, email=None):
        import getpass
        import ssl

        self.server = server or input("Type your SMTP server and press enter: ")
        if port is None:
            port = input(f"On which port does the SMTP server {self.server} answer (default: 587)? ") or 587
        self.port: int = int(port)

        if username is None:
            username = input(f"What is your username for {self.server}? ")
        self.username = username

        if email is None:
            default_sender = "@".join((self.username, self.server.removeprefix("smtp.")))
            email = input(f"What is the from address for {self.username}@{self.server} (default {default_sender})? ") or default_sender
        self.sender_email = email

        self.password = getpass.getpass(f"Type your password for {self.username}@{self.server} and press enter: ")

        self.context = ssl.create_default_context()

    def __enter__(self):
        import smtplib

        self.conn = smtplib.SMTP(self.server, self.port)
        self.conn.ehlo()
        self.conn.starttls(context=self.context)
        self.conn.ehlo()
        self.conn.login(self.username, self.password)
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.conn.quit()


def compose_mime_message(sender, recipient, subject, body, attachments):
    from email import encoders
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Bcc"] = sender

    message.attach(MIMEText(body, "plain"))

    for path in attachments:
        with pathlib.Path(path).open("rb") as file:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(file.read())
        encoders.encode_base64(part)

        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {path.name}",
        )

        message.attach(part)

    return message.as_string()


class MailExporter(ExportPlugin):
    """
    Send feedback by mail.

    Requires additional configuration file `self.config.ExportPlugin.config`
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # TODO: Ensure that this works as expected
        self.export_config = read_config(self.config["ExportPlugin"].get("config"))

    def export(self, gradebook):
        # TODO: Refactor: Extract message composition from templates
        students = list(map(gradebook.find_student, self.student)) or gradebook.students

        assignments = list(map(gradebook.find_assignment, self.assignment)) or gradebook.assignments

        grades_table = (
            export_to_multiindex(
                gradebook,
                students,
                assignments,
                missing_ok=self.export_config["feedback"].get("missing_ok"),
            )
            .round(2)
            .sample(axis=1, frac=1.0, random_state=6)
        )

        reachable = grades_table["reachable"]
        if reachable.apply(float.is_integer).all():
            reachable = reachable.astype(int)

        format_assignment = {
            "assignment_id": '", "'.join(str(a.name) for a in assignments),
            "points_max": reachable.sum(),
            "points_100_percent": self.export_config["grading"].get("points_100_percent"),
            "sender": self.export_config["mail_data"].get("sender"),
        }

        with SMTPConnection(**self.export_config["mail_data"]["smtp"]) as smtp:
            for student_id, results in grades_table.items():
                if student_id == "reachable":
                    continue

                student = gradebook.find_student(str(student_id))
                details = format_details(results, reachable)

                address_book = {key: value["email"] for key, value in self.export_config["mail_data"]["address_book"].items()} | {
                    "students": student.email
                }

                if self.export_config["feedback"]["attach"]:
                    feedback_files = self.export_config["feedback"]["location"]
                    if not feedback_files:
                        feedback_files = self.config["CourseDirectory"].get("directory_structure")
                    if not feedback_files:
                        self.log.warning("Unsure where to find feedback. Trying nbgrader default.")
                        feedback_files = "{nbgrader_step}/{student_id}/{assignment_id}"
                    feedback_files = feedback_files + r"/{notebook_name}" + self.export_config["feedback"]["suffix"]
                    attachments = find_attachments(
                        feedback_files,
                        student_id,
                        assignments,
                    )

                    if attachments:
                        self.log.info(f"found {len(attachments)} feedback files to attach.")
                    elif not self.export_config["feedback"]["missing_ok"]:
                        self.log.info(f"Skipping student {student.id} ({student.first_name} {student.last_name}):No feedback files found.")
                        continue
                else:
                    attachments = []

                points_reached = results.sum()
                if grading := self.export_config["grading"].get("percentage_to_grade"):
                    grade = grading(points_reached * 100 / self.export_config["grading"]["points_100_percent"])
                else:
                    grade = None

                if results.isna().all().all():
                    passed = None
                else:
                    passed = points_reached >= self.export_config["grading"].get("points_needed", 0)
                admitted = self.export_config["grading"].get("default_admission") or bool(passed)

                format_student = {
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "points_reached": points_reached,
                    # TODO: percentage_reached (?)
                    "details": details.to_string(),
                    "message_pass_fail": (self.export_config.get("grading").get("message_pass_fail").get(str(admitted))),
                    "grade": grade,
                }

                # write out additional information depending on the result
                body = self.export_config["message_templates"]["header"]
                if self.export_config["appointments"].get(str(admitted)):
                    termin, ort = next(self.export_config["appointments"][str(admitted)][0])
                    self.export_config["appointments"][str(admitted)][1][termin].append(f"{student.last_name}, {student.first_name}")
                    format_student["exam_info"] = f"{termin} in {ort}"

                for check, value in {
                    "if_participated": str(passed is not None),
                    "if_passed": str(passed),
                    "if_admitted": str(admitted),
                }.items():
                    if self.export_config["message_templates"].get(check) is not None:
                        more_info = self.export_config["message_templates"][check].get(value)
                        if more_info is not None:
                            body += more_info + "\n"

                body += self.export_config["message_templates"]["footer"]

                body = body.format(
                    **format_assignment,
                    **format_student,
                )

                subject = self.export_config["message_templates"]["subject"].format(
                    module_name=os.getenv("COURSE_TITLE"),
                    result=self.export_config["module"].get("exam_type"),
                    type="information" if passed is None else "ergebnis",
                )

                message = compose_mime_message(
                    sender=smtp.sender_email,
                    recipient=address_book["students"],
                    subject=subject,
                    body=body,
                    attachments=attachments,
                )

                to_addrs = list(f"{{{self.to}}}".replace(",", "};{").format_map(address_book).split(";"))

                if not to_addrs:
                    self.log.info(f"Recipient not {'recognized' if self.to else 'given'}.")
                    self.log.info(f"Dry run: not sending to {address_book['students']}.")
                    continue

                self.log.info("Sending e-mail to %s.", to_addrs)
                send_mail(message, smtp, to_addrs, log=self.log)
                # TODO: Optionally add a sleeping time to bypass SMTP rate limits

            # send summary message to instructors
            if self.export_config["appointments"] is not None:
                body = ""
                for reason, appointments in self.export_config["appointments"].items():
                    body += f"Appointments for students who {reason}:\n"
                    body += pd.DataFrame(
                        data=list(itertools.zip_longest(*appointments[1].values(), fillvalue="")),
                        columns=pd.Index(appointments[1].keys()),
                    ).to_string(max_rows=None, max_cols=None)
                    body += "\n\n"

                address_book = {key: value["email"] for key, value in self.export_config["mail_data"]["address_book"].items()} | {
                    "students": smtp.sender_email
                }

                to_addrs = list(f"{{{self.to}}}".replace(",", "};{").format_map(address_book).split(";"))

                message = compose_mime_message(
                    sender=smtp.sender_email,
                    recipient=smtp.sender_email,
                    subject=self.export_config["message_templates"]["subject"],
                    body=body,
                    attachments=[],
                )

                self.log.info("Sending summary e-mail to %s.", to_addrs)
                send_mail(message, smtp, to_addrs)
