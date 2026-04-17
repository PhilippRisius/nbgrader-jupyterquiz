function check_numeric(ths, event) {

    if (event.keyCode === 13) {
        ths.blur();

        var id = ths.id.split('-')[0];
        var hideMode = (ths.dataset.hide == "true");

        var submission = ths.value;
        if (submission.indexOf('/') != -1) {
            var sub_parts = submission.split('/');
            submission = sub_parts[0] / sub_parts[1];
        }

        if (("precision" in ths.dataset) && (ths.dataset.precision > 0)) {
            var precision = ths.dataset.precision;
            submission = Number(Number(submission).toPrecision(precision));
        }

        var fb = document.getElementById("fb" + id);
        fb.style.display = "none";
        fb.innerHTML = "Incorrect -- try again.";

        var answers = JSON.parse(ths.dataset.answers);

        var defaultFB = "Incorrect. Try again.";
        var correct;
        var done = false;
        answers.every(answer => {
            correct = false;
            if ('value' in answer) {
                var value;
                if ("precision" in ths.dataset) {
                    value = answer.value.toPrecision(ths.dataset.precision);
                } else {
                    value = answer.value;
                }
                if (submission == value) {
                    if ("feedback" in answer) {
                        fb.innerHTML = jaxify(answer.feedback);
                    } else {
                        fb.innerHTML = jaxify("Correct");
                    }
                    correct = answer.correct;
                    done = true;
                }
            } else if ('range' in answer) {
                // Inclusive on both ends — matches the quiz-syntax semantics
                // documented for ``+ [min, max]`` and the Python autograder's
                // grade_numeric().  Previously used a strict `<` on the upper
                // bound, which rejected ``max`` as incorrect.  Force a
                // numeric coercion of the submission because earlier branches
                // (fraction / precision) already normalise to a Number, but
                // the plain-input path leaves it as a string.
                var numSub = Number(submission);
                if (Number.isFinite(numSub) && numSub >= answer.range[0] && numSub <= answer.range[1]) {
                    if ("feedback" in answer) {
                        fb.innerHTML = jaxify(answer.feedback);
                    } else {
                        fb.innerHTML = jaxify("Correct");
                    }
                    correct = answer.correct;
                    done = true;
                }
            } else if (answer.type == "default") {
                if ("feedback" in answer) {
                    defaultFB = answer.feedback;
                }
            }
            if (done) {
                return false;
            } else {
                return true;
            }
        });

        if ((!done) && (defaultFB != "")) {
            fb.innerHTML = jaxify(defaultFB);
        }

        fb.style.display = "block";

        // Feedback styling: hide mode shows a neutral "Recorded." state;
        // legacy mode reveals correctness via correct/incorrect colouring.
        if (hideMode) {
            ths.className = "Input-text";
            ths.classList.add("selectedButton");
            fb.className = "Feedback";
            fb.classList.remove("deselected");
            fb.classList.add("selected");
            fb.innerHTML = (submission === "" || submission === null || Number.isNaN(Number(submission)))
                ? "Cleared."
                : "Answer recorded: " + submission + ".";
        } else if (correct) {
            ths.className = "Input-text";
            ths.classList.add("correctButton");
            fb.className = "Feedback";
            fb.classList.add("correct");
        } else {
            ths.className = "Input-text";
            ths.classList.add("incorrectButton");
            fb.className = "Feedback";
            fb.classList.add("incorrect");
        }

        // What follows is for the saved responses stuff
        var outerContainer = fb.parentElement.parentElement;
        var responsesContainer = document.getElementById("responses" + outerContainer.id);
        if (responsesContainer) {
            console.log(submission);
            var qnum = document.getElementById("quizWrap"+id).dataset.qnum;
            //console.log("Question " + qnum);
            //console.log(id, ", got numcorrect=",fb.dataset.numcorrect);
            var responses=JSON.parse(responsesContainer.dataset.responses);
            console.log(responses);
            if (submission == ths.value){
                responses[qnum]= submission;
            } else {
                responses[qnum]= ths.value + "(" + submission +")";
            }
            responsesContainer.setAttribute('data-responses', JSON.stringify(responses));
            printResponses(responsesContainer);
        }
        // End code to preserve responses

        // Sidecar recorder (no-op without data-grade-id)
        var __gradeId = outerContainer.dataset.gradeId;
        if (__gradeId) {
            var __qnum = document.getElementById("quizWrap"+id).dataset.qnum;
            var __parsed = Number.isFinite(Number(submission)) ? Number(submission) : submission;
            recordResponse(__gradeId, __qnum, {
                type: "numeric",
                raw: ths.value,
                parsed: __parsed,
            });
        }

        if (typeof MathJax != 'undefined') {
            var version = MathJax.version;
            console.log('MathJax version', version);
            if (version[0] == "2") {
                MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
            } else if (version[0] == "3") {
                MathJax.typeset([fb]);
            }
        } else {
            console.log('MathJax not detected');
        }
        // Auto-advance focus to the next text-input quiz item.  In legacy
        // mode we only advance on correct; in hide mode we advance on any
        // submission since correctness isn't revealed.
        if (correct || hideMode) {
            var wrapper = ths.closest('.Quiz');
            if (wrapper) {
                var nextWrapper = wrapper.nextElementSibling;
                if (nextWrapper && nextWrapper.classList.contains('Quiz')) {
                    var nextInput = nextWrapper.querySelector('input.Input-text');
                    if (nextInput) {
                        nextInput.focus();
                    }
                }
            }
        }
        return false;
    }

}
// Object-oriented wrapper for numeric questions
class NumericQuestion extends Question {
    constructor(qa, id, idx, opts, rootDiv) {
        super(qa, id, idx, opts, rootDiv);
    }
    render() {
        make_numeric(this.qa, this.outerqDiv, this.qDiv, this.aDiv, this.id);
        this.wrapper.appendChild(this.fbDiv);
    }
}
Question.register('numeric', NumericQuestion);

function isValid(el, charC) {
    //console.log("Input char: ", charC);
    if (charC == 46) {
        if (el.value.indexOf('.') === -1) {
            return true;
        } else if (el.value.indexOf('/') != -1) {
            var parts = el.value.split('/');
            if (parts[1].indexOf('.') === -1) {
                return true;
            }
        }
        else {
            return false;
        }
    } else if (charC == 47) {
        if (el.value.indexOf('/') === -1) {
            if ((el.value != "") && (el.value != ".")) {
                return true;
            } else {
                return false;
            }
        } else {
            return false;
        }
    } else if (charC == 45) {
        var edex = el.value.indexOf('e');
        if (edex == -1) {
            edex = el.value.indexOf('E');
        }

        if (el.value == "") {
            return true;
        } else if (edex == (el.value.length - 1)) { // If just after e or E
            return true;
        } else {
            return false;
        }
    } else if (charC == 101) { // "e"
        if ((el.value.indexOf('e') === -1) && (el.value.indexOf('E') === -1) && (el.value.indexOf('/') == -1)) {
            // Prev symbol must be digit or decimal point:
            if (el.value.slice(-1).search(/\d/) >= 0) {
                return true;
            } else if (el.value.slice(-1).search(/\./) >= 0) {
                return true;
            } else {
                return false;
            }
        } else {
            return false;
        }
    } else {
        if (charC > 31 && (charC < 48 || charC > 57))
            return false;
    }
    return true;
}

function numeric_keypress(evnt) {
    var charC = (evnt.which) ? evnt.which : evnt.keyCode;

    if (charC == 13) {
        check_numeric(this, evnt);
    } else {
        return isValid(this, charC);
    }
}





function make_numeric(qa, outerqDiv, qDiv, aDiv, id) {



    //console.log(answer);


    outerqDiv.className = "NumericQn";
    aDiv.style.display = 'block';

    var lab = document.createElement("label");
    lab.className = "InpLabel";
    lab.innerHTML = "Type numeric answer here:";
    aDiv.append(lab);

    var inp = document.createElement("input");
    inp.type = "text";
    inp.id = id + "-0";
    inp.className = "Input-text";
    inp.setAttribute('data-answers', JSON.stringify(qa.answers));
    if ("precision" in qa) {
        inp.setAttribute('data-precision', qa.precision);
    }
    if (qa.hide) {
        inp.setAttribute('data-hide', "true");
    }
    aDiv.append(inp);
    //console.log(inp);

    //inp.addEventListener("keypress", check_numeric);
    //inp.addEventListener("keypress", numeric_keypress);
    /*
    inp.addEventListener("keypress", function(event) {
        return numeric_keypress(this, event);
    }
                        );
                        */
    //inp.onkeypress="return numeric_keypress(this, event)";
    inp.onkeypress = numeric_keypress;
    inp.onpaste = event => false;

    inp.addEventListener("focus", function (event) {
        this.value = "";
        return false;
    }
    );


}
