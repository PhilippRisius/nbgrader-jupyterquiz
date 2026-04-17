/* Callback function to determine whether a selected multiple-choice
   button corresponded to a correct answer and to provide feedback
   based on the answer.

   Supports two modes per answer (via item.hide in the quiz JSON):
   - hide=false (default): click reveals correct/incorrect (legacy).
   - hide=true: click toggles a neutral Selected / Deselected state;
     no correctness feedback is shown.  Intended for graded quizzes
     where immediate feedback would allow the student to guess until
     right.
   Propagated at the quiz level via the "hide_correctness=true" quiz
   option in #### Quiz headers (see parse.parse_cell). */
function check_mc() {
    // `this` is the clicked button element (each answer is a <button>
    // registered with btn.onclick = check_mc in make_mc).  Using a
    // <button> instead of the old <label>+hidden-<input> avoids the
    // browser's label→radio click synthesis that double-fired this
    // handler and broke the hide-mode toggle.
    var label = this;
    var id = label.id.split('-')[0];
    var answers = label.parentElement.children;
    var fb = document.getElementById("fb" + id);
    var hideMode = (label.dataset.hide == "true");

    if (fb.dataset.numcorrect <= 1) {
        /* ----- Single-choice path ----- */
        var outerContainer = fb.parentElement.parentElement;
        var response = (label.innerText || label.textContent || "").trim();
        var qnum = document.getElementById("quizWrap"+id).dataset.qnum;

        // Existing DOM data-responses update (only when preserve_responses=true).
        var responsesContainer = document.getElementById("responses" + outerContainer.id);
        if (responsesContainer) {
            var responses = JSON.parse(responsesContainer.dataset.responses);
            if (hideMode && label.dataset.selected == "true") {
                // Clicking an already-selected SC answer in hide mode deselects it.
                responses[qnum] = null;
            } else {
                responses[qnum] = response;
            }
            responsesContainer.setAttribute('data-responses', JSON.stringify(responses));
            printResponses(responsesContainer);
        }

        // Visual reset of siblings (radio-like behaviour).
        for (var i = 0; i < answers.length; i++) {
            var child = answers[i];
            if (child.id != label.id) {
                if (child.classList.contains("selectedButton")) {
                    child.setAttribute('data-selected', "false");
                    child.classList.remove("selectedButton");
                    void child.offsetWidth;
                    child.classList.add("deselectedButton");
                }
                if (child.classList.contains("correctButton")) child.classList.remove("correctButton");
                if (child.classList.contains("incorrectButton")) child.classList.remove("incorrectButton");
            }
        }

        if (hideMode) {
            // Toggle select / deselect on the clicked label — no correctness hint.
            if (label.dataset.selected == "true") {
                label.setAttribute('data-selected', "false");
                label.classList.remove("selectedButton");
                void label.offsetWidth;
                label.classList.add("deselectedButton");
                fb.innerHTML = 'Deselected: "' + response + '".';
                fb.classList.remove("selected");
                fb.classList.add("deselected");
            } else {
                label.setAttribute('data-selected', "true");
                if ("feedback" in label.dataset) {
                    fb.innerHTML = jaxify(label.dataset.feedback);
                } else {
                    fb.innerHTML = 'Selected: "' + response + '".';
                }
                label.classList.remove("deselectedButton");
                void label.offsetWidth;
                label.classList.add("selectedButton");
                fb.className = "Feedback";
                fb.classList.remove("deselected");
                fb.classList.add("selected");
            }
        } else {
            // Legacy: show correctness feedback.
            if (label.dataset.correct == "true") {
                if ("feedback" in label.dataset) {
                    fb.innerHTML = jaxify(label.dataset.feedback);
                } else {
                    fb.innerHTML = "Correct!";
                }
                label.classList.add("correctButton");
                fb.className = "Feedback";
                fb.classList.add("correct");
            } else {
                if ("feedback" in label.dataset) {
                    fb.innerHTML = jaxify(label.dataset.feedback);
                } else {
                    fb.innerHTML = "Incorrect -- try again.";
                }
                label.classList.add("incorrectButton");
                fb.className = "Feedback";
                fb.classList.add("incorrect");
            }
        }

        // Sidecar recorder (no-op without data-grade-id).  In hide mode we
        // record whatever is currently selected (null when deselected); in
        // legacy mode we record each click's target.
        var __gradeId = outerContainer.dataset.gradeId;
        if (__gradeId) {
            var __selected;
            if (hideMode) {
                __selected = (label.dataset.selected == "true") ? response : null;
            } else {
                __selected = response;
            }
            recordResponse(__gradeId, qnum, {
                type: "multiple_choice",
                selected: __selected,
            });
        }
    } else {
        /* ----- Many-choice path ----- */
        var outerContainer = fb.parentElement.parentElement;
        var response = (label.innerText || label.textContent || "").trim();
        var qnum = document.getElementById("quizWrap"+id).dataset.qnum;
        var reset = false;
        var feedback;

        if (hideMode) {
            // Toggle selection on the clicked label — no correctness hint.
            if (label.dataset.selected == "true") {
                label.setAttribute('data-selected', "false");
                label.classList.remove("selectedButton");
                void label.offsetWidth;
                label.classList.add("deselectedButton");
                feedback = 'Deselected: "' + response + '".';
                fb.classList.remove("selected");
                fb.classList.add("deselected");
            } else {
                label.setAttribute('data-selected', "true");
                if ("feedback" in label.dataset) {
                    feedback = jaxify(label.dataset.feedback);
                } else {
                    feedback = 'Selected: "' + response + '".';
                }
                label.classList.remove("deselectedButton");
                void label.offsetWidth;
                label.classList.add("selectedButton");
                fb.className = "Feedback";
                fb.classList.remove("deselected");
                fb.classList.add("selected");
            }
        } else {
            // Legacy: correct click accumulates, wrong click resets.
            if (label.dataset.correct == "true") {
                if ("feedback" in label.dataset) {
                    feedback = jaxify(label.dataset.feedback);
                } else {
                    feedback = "Correct!";
                }
                if (label.dataset.answered <= 0) {
                    if (fb.dataset.answeredcorrect < 0) {
                        fb.dataset.answeredcorrect = 1;
                        reset = true;
                    } else {
                        fb.dataset.answeredcorrect++;
                    }
                    if (reset) {
                        for (var i = 0; i < answers.length; i++) {
                            var child = answers[i];
                            if (child.id != label.id) {
                                if (child.dataset.selected == "true") {
                                    child.setAttribute('data-selected', "false");
                                    child.classList.remove("selectedButton");
                                    void child.offsetWidth;
                                    child.classList.add("deselectedButton");
                                }
                                if (child.classList.contains("correctButton")) child.classList.remove("correctButton");
                                if (child.classList.contains("incorrectButton")) child.classList.remove("incorrectButton");
                                child.dataset.answered = 0;
                            }
                        }
                    }
                    label.classList.add("correctButton");
                    label.dataset.answered = 1;
                    fb.className = "Feedback";
                    fb.classList.add("correct");
                }
            } else {
                if ("feedback" in label.dataset) {
                    feedback = jaxify(label.dataset.feedback);
                } else {
                    feedback = "Incorrect -- try again.";
                }
                if (fb.dataset.answeredcorrect > 0) {
                    fb.dataset.answeredcorrect = -1;
                    reset = true;
                } else {
                    fb.dataset.answeredcorrect--;
                }
                if (reset) {
                    for (var i = 0; i < answers.length; i++) {
                        var child = answers[i];
                        if (child.id != label.id) {
                            if (child.dataset.selected == "true") {
                                child.setAttribute('data-selected', "false");
                                child.classList.remove("selectedButton");
                                void child.offsetWidth;
                                child.classList.add("deselectedButton");
                            }
                            if (child.classList.contains("correctButton")) child.classList.remove("correctButton");
                            if (child.classList.contains("incorrectButton")) child.classList.remove("incorrectButton");
                            child.dataset.answered = 0;
                        }
                    }
                }
                label.classList.add("incorrectButton");
                fb.className = "Feedback";
                fb.classList.add("incorrect");
            }
        }

        // DOM data-responses update (unified Set-based — a click toggles
        // the response's presence, treating correct and incorrect alike).
        var responsesContainer = document.getElementById("responses" + outerContainer.id);
        if (responsesContainer) {
            var responses = JSON.parse(responsesContainer.dataset.responses);
            var these_responses;
            if (typeof(responses[qnum]) == "object" && responses[qnum] !== null) {
                these_responses = new Set(responses[qnum]);
            } else {
                these_responses = new Set();
            }
            if (label.dataset.selected == "true") {
                these_responses.add(response);
            } else {
                these_responses.delete(response);
            }
            responses[qnum] = Array.from(these_responses);
            responsesContainer.setAttribute('data-responses', JSON.stringify(responses));
            printResponses(responsesContainer);
        }

        // Sidecar recorder (no-op without data-grade-id).  Source of truth
        // is data-selected when hide mode is active; .correctButton is the
        // legacy fallback.
        var __gradeId = outerContainer.dataset.gradeId;
        if (__gradeId) {
            var __selected = [];
            for (var __i = 0; __i < answers.length; __i++) {
                var __ans = answers[__i];
                var __match;
                if (hideMode) {
                    __match = __ans.dataset && __ans.dataset.selected == "true";
                } else {
                    __match = __ans.classList && __ans.classList.contains('correctButton');
                }
                if (__match) {
                    __selected.push((__ans.innerText || __ans.textContent || "").trim());
                }
            }
            recordResponse(__gradeId, qnum, {
                type: "many_choice",
                selected: __selected,
            });
        }

        // Feedback display: the legacy "N/M correct" counter leaks the
        // total number of correct answers, so in hide mode we suppress it.
        if (hideMode) {
            fb.innerHTML = feedback;
        } else {
            var numcorrect = fb.dataset.numcorrect;
            var answeredcorrect = fb.dataset.answeredcorrect;
            if (answeredcorrect >= 0) {
                fb.innerHTML = feedback + " [" + answeredcorrect + "/" + numcorrect + "]";
            } else {
                fb.innerHTML = feedback + " [" + 0 + "/" + numcorrect + "]";
            }
        }
    }

    if (typeof MathJax != 'undefined') {
        var version = MathJax.version;
        if (version[0] == "2") {
            MathJax.Hub.Queue(["Typeset", MathJax.Hub]);
        } else if (version[0] == "3") {
            MathJax.typeset([fb]);
        }
    }
}


/* Function to produce the HTML buttons for a multiple choice /
   many choice question and to update the CSS tags based on the
   question type.

   Uses a plain <button type="button"> per answer.  The previous
   <label>+<input type="radio"> pattern caused click events to fire
   twice on each user click (once for the original target, once for
   the browser-synthesized click on the radio), which broke hide-mode
   toggle semantics. */
function make_mc(qa, shuffle_answers, outerqDiv, qDiv, aDiv, id) {

    var shuffled;
    if (shuffle_answers == true) {
        shuffled = getRandomSubarray(qa.answers, qa.answers.length);
    } else {
        shuffled = qa.answers;
    }

    var num_correct = 0;

    shuffled.forEach((item, index, ans_array) => {
        var btn = document.createElement("button");
        btn.type = "button"; // prevent any enclosing-form submit semantics
        btn.className = "MCButton";
        btn.id = id + '-' + index;
        btn.onclick = check_mc;

        var aSpan = document.createElement('span');
        if ("answer" in item) {
            aSpan.innerHTML = jaxify(item.answer);
        }
        btn.append(aSpan);

        // Optional inline code block
        if ("code" in item) {
            var codeSpan = document.createElement('span');
            codeSpan.id = "code" + id + index;
            codeSpan.className = "QuizCode";
            var codePre = document.createElement('pre');
            codeSpan.append(codePre);
            var codeCode = document.createElement('code');
            codePre.append(codeCode);
            codeCode.innerHTML = item.code;
            btn.append(codeSpan);
        }

        // Selection state (always starts false).
        btn.setAttribute('data-selected', "false");

        // Hide-correctness flag for this answer.
        if ("hide" in item) {
            btn.setAttribute('data-hide', item.hide);
        } else {
            btn.setAttribute('data-hide', "false");
        }

        // Correctness metadata (always set for SC/many decision via numcorrect).
        btn.setAttribute('data-correct', item.correct);
        if (item.correct) {
            num_correct++;
        }
        if ("feedback" in item) {
            btn.setAttribute('data-feedback', item.feedback);
        }
        btn.setAttribute('data-answered', 0);

        aDiv.append(btn);
    });

    if (num_correct > 1) {
        outerqDiv.className = "ManyChoiceQn";
    } else {
        outerqDiv.className = "MultipleChoiceQn";
    }

    return num_correct;
}


// Object-oriented wrapper for MC/MANY choice
class MCQuestion extends Question {
    constructor(qa, id, idx, opts, rootDiv) { super(qa, id, idx, opts, rootDiv); }
    render() {
        const numCorrect = make_mc(
            this.qa,
            this.options.shuffleAnswers,
            this.outerqDiv,
            this.qDiv,
            this.aDiv,
            this.id
        );
        if ('answer_cols' in this.qa) {
            this.aDiv.style.gridTemplateColumns =
                'repeat(' + this.qa.answer_cols + ', 1fr)';
        }
        this.fbDiv.dataset.numcorrect = numCorrect;
        this.wrapper.appendChild(this.fbDiv);
    }
}
Question.register('multiple_choice', MCQuestion);
Question.register('many_choice', MCQuestion);
