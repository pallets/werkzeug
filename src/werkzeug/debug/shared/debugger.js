function fadeOut(element){
    element.style.opacity = 1;

    (function fade() {
        element.style.opacity -= .1
        if (element.style.opacity < 0) {
            element.style.display = "none";
        } else {
            requestAnimationFrame(fade);
        }
    })();
}

function fadeIn(element, display){
    element.style.opacity = 0;
    element.style.display = display || "block";

    (function fade() {
        let val = parseFloat(element.style.opacity) + 0.1;
        if (val <= 1) {
            element.style.opacity = val;
            requestAnimationFrame(fade);
        }
    })();
}

docReady(function() {
    if (!EVALEX_TRUSTED) {
        initPinBox();
    }
    // if we are in console mode, show the console.
    if (CONSOLE_MODE && EVALEX) {
        openShell(null, $('div.console div.inner').empty(), 0);
    }
    addEventListenersToElements(document.querySelectorAll('div.detail'),
        'click', () => document.querySelectorAll('div.traceback')[0].scrollIntoView(false));
    addConsoleIconToFrames(document.querySelectorAll('div.traceback div.frame'));
    addToggleTraceTypesOnClick(document.querySelectorAll('h2.traceback'));
    addInfoPrompt(document.querySelectorAll('span.nojavascript'));
    plainTraceback(document.querySelectorAll('div.plain, textarea'));
});

function initPinBox() {
    document.querySelector(".pin-prompt form")
        .addEventListener("submit", function(event) {
            event.preventDefault();
            const pin = encodeURIComponent(this.pin.value);
            const encodedSecret = encodeURIComponent(SECRET);
            const btn = this.btn;
            btn.disabled = true;

            fetch(`${document.location.pathname}?__debugger__=yes&cmd=pinauth&pin=${pin}&s=${encodedSecret}`)
            .then(res => res.json())
            .then(({ auth, exhausted }) => {
                if (auth) {
                    EVALEX_TRUSTED = true;
                    fadeOut(document.getElementsByClassName("pin-prompt")[0]);
                } else {
                    alert(`Error: ${exhausted
                        ? "too many attempts.  Restart server to retry."
                        : "incorrect pin"}`)
                }
            })
            .catch(err => {
                alert('Error: Could not verify PIN.  Network error?');
                console.error(err);
            })
            .finally(() => btn.disabled = false);
        }, false);
}

function promptForPin() {
    if (!EVALEX_TRUSTED) {
        const encodedSecret = encodeURIComponent(SECRET);
        fetch(`${document.location.pathname}?__debugger__=yes&cmd=printpin&s=${encodedSecret}`);
        const pinPrompt = document.getElementsByClassName("pin-prompt")[0];
        fadeIn(pinPrompt);
        document.querySelector('.pin-prompt input[name="pin"]').focus();
    }
}

/**
 * Helper function for shell initialization
 */
function openShell(consoleNode, target, frameID) {
    promptForPin();
    if (consoleNode) {
        slideToggle(consoleNode);
        return consoleNode;
    }

    let historyPos = 0;
    let history = [''];

    consoleNode = createConsole();
    let output = createConsoleOutput();
    let form = createConsoleInputForm();
    let command = createConsoleInput();

    target.parentNode.appendChild(consoleNode);
    consoleNode.append(output);
    consoleNode.append(form);
    form.append(command);
    command.focus();
    slideToggle(consoleNode);

    form.addEventListener('submit', e => {
        handleConsoleSubmit(e, command, frameID).then(consoleOutput => {
            output.append(consoleOutput);
            command.focus();
            consoleNode.scrollTo(0, consoleNode.scrollHeight);
            let old = history.pop();
            history.push(command.value);
            if (typeof old != 'undefined') {
                history.push(old);
            }
            historyPos = history.length - 1;
            command.value = '';
        });
    });

    command.addEventListener('keydown', function(e) {
        if (e.key == 'l' && e.ctrlKey) {
            output.innerText = '--- screen cleared ---';
        } else if (e.charCode == 0 && (e.keyCode == 38 || e.keyCode == 40)) {
            // Handle up arrow and down arrow.
            if (e.keyCode == 38 && historyPos > 0) {
                historyPos--;
            } else if (e.keyCode == 40 && historyPos < history.length - 1) {
                historyPos++;
            }
            command.value = history[historyPos];
        }
        return false;
    });

    return consoleNode;
}

function addEventListenersToElements(elements, typeOfEvent, typeOfListener) {
    for (let i = 0; i < elements.length; i++) {
        elements[i].addEventListener(typeOfEvent, typeOfListener);
    }
}

/**
 * Add extra info
 */
function addInfoPrompt(elements) {
    for (let i = 0; i < elements.length; i++) {
        elements[i].innerHTML = '<p>To switch between the interactive traceback and the plaintext ' +
            'one, you can click on the "Traceback" headline. From the text ' +
            'traceback you can also create a paste of it. ' + (!EVALEX ? '' :
                'For code execution mouse-over the frame you want to debug and ' +
                'click on the console icon on the right side.' +
                '<p>You can execute arbitrary Python code in the stack frames and ' +
                'there are some extra helpers available for introspection:' +
                '<ul><li><code>dump()</code> shows all variables in the frame' +
                '<li><code>dump(obj)</code> dumps all that\'s known about the object</ul>')
        elements[i].classList.remove('nojavascript')
    }
}

function addConsoleIconToFrames(frames) {
    let consoleNode = null;
    for (let i = 0; i < frames.length; i++) {
        let target = frames[i];
        let frameID = frames[i].id.substring(6);
        target.addEventListener('click', () => {
            target.getElementsByTagName('pre')[i].parentElement.classList.toggle('expanded');
        });

        for (let j = 0; j < target.getElementsByTagName('pre').length; j++) {
            let img = createIconForConsole();
            img.addEventListener('click', (e) => {
                e.stopPropagation();
                consoleNode = openShell(consoleNode, target, frameID);
                return false;
            });
            target.getElementsByTagName('pre')[j].append(img);
        }
    }
}

function slideToggle(target) {
    target.classList.toggle('active');
}

/**
 * toggle traceback types on click.
 */
function addToggleTraceTypesOnClick(elements) {
    for (let i = 0; i < elements.length; i++) {
        elements[i].addEventListener('click', () => {
            $(this).next().slideToggle('fast');
            $('div.plain').slideToggle('fast');
        });
        elements[i].style.cursor = 'pointer';
        document.querySelector('div.plain').style.display = 'none';
    }
}

function plainTraceback(elements) {
    elements.replaceWith($('<pre>').text(plainTraceback.text()))
}

function createConsole() {
    let consoleNode = document.createElement('pre');
    consoleNode.classList.add('console');
    consoleNode.classList.add('active');
    return consoleNode;
}

function createConsoleOutput() {
    let output = document.createElement('div');
    output.classList.add('output');
    output.innerHTML = '[console ready]';
    return output;
}

function createConsoleInputForm() {
    let form = document.createElement('form');
    form.innerHTML = '&gt;&gt;&gt; ';
    return form;
}

function createConsoleInput() {
    let command = document.createElement('input');
    command.type = 'text';
    command.setAttribute('autocomplete', 'off');
    command.setAttribute('spellcheck', false);
    command.setAttribute('autocapitalize', 'off');
    command.setAttribute('autocorrect', 'off');
    return command;
}

function createIconForConsole() {
    let img = document.createElement('img');
    img.setAttribute('src', '?__debugger__=yes&cmd=resource&f=console.png');
    img.setAttribute('title', 'Open an interactive python shell in this frame');
    return img;
}

function handleConsoleSubmit(e, command, frameID) {
    // Prevent page from refreshing.
    e.preventDefault();

    return new Promise((resolve, reject) => {
        // Get input command.
        let cmd = command.value;

        // Setup GET request.
        let urlPath = '';
        let params = {
            __debugger__: 'yes',
            cmd: cmd,
            frm: frameID,
            s: SECRET
        };
        let paramString = Object.keys(params).map(key => {
            return '&' + encodeURIComponent(key) + '=' + encodeURIComponent(params[key]);
        }).join('');

        fetch(urlPath + '?' + paramString).then(res => {
            return res.text()
        }).then(data => {
            let tmp = document.createElement('div');
            tmp.innerHTML = data;
            resolve(tmp);
            $('span.extended', tmp).each(function() {
                var hidden = $(this).wrap('<span>').hide();
                hidden.parent().append($('<a href="#" class="toggle">&nbsp;&nbsp;</a>')
                    .click(function() {
                        hidden.toggle();
                        $(this).toggleClass('open')
                        return false;
                    }));
            });
        }).catch(err => {
            console.error(err);
        });
        return false;
    });
}

function docReady(fn) {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        setTimeout(fn, 1);
    } else {
        document.addEventListener('DOMContentLoaded', fn);
    }
}
