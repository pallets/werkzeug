docReady(function() {
  if (!EVALEX_TRUSTED) {
    initPinBox();
  }
  // if we are in console mode, show the console.
  if (CONSOLE_MODE && EVALEX) {
    openShell(null, $('div.console div.inner').empty(), 0);
  }
  addEventListenersToElements(document.querySelectorAll("div.detail"),
    'click', () => document.querySelectorAll("div.traceback")[0].scrollIntoView(false));
  addConsoleIconToFrames(document.querySelectorAll("div.traceback div.frame"));
  addToggleTraceTypesOnClick(document.querySelectorAll('h2.traceback'));
  addInfoPrompt(document.querySelectorAll("span.nojavascript"));
  plainTraceback(document.querySelectorAll('div.plain, textarea'));
});

function initPinBox() {
    $('.pin-prompt form').submit(function(evt) {
        evt.preventDefault();
        var pin = this.pin.value;
        var btn = this.btn;
        btn.disabled = true;
        $.ajax({
            dataType: 'json',
            url: document.location.pathname,
            data: {
                __debugger__: 'yes',
                cmd: 'pinauth',
                pin: pin,
                s: SECRET
            },
            success: function(data) {
                btn.disabled = false;
                if (data.auth) {
                    EVALEX_TRUSTED = true;
                    $('.pin-prompt').fadeOut();
                } else {
                    if (data.exhausted) {
                        alert('Error: too many attempts.  Restart server to retry.');
                    } else {
                        alert('Error: incorrect pin');
                    }
                }
                console.log(data);
            },
            error: function() {
                btn.disabled = false;
                alert('Error: Could not verify PIN.  Network error?');
            }
        });
    });
}

function promptForPin() {
    if (!EVALEX_TRUSTED) {
        $.ajax({
            url: document.location.pathname,
            data: { __debugger__: 'yes', cmd: 'printpin', s: SECRET }
        });
        $('.pin-prompt').fadeIn(function() {
            $('.pin-prompt input[name="pin"]').focus();
        });
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
    const history = [''];

    consoleNode = createConsole();
    const output = createConsoleOutput();
    const form = createConsoleInputForm();
    const command = createConsoleInput();
    target.parentNode.appendChild(consoleNode);
    consoleNode.append(output);
    consoleNode.append(form);
    form.append(command);
    command.focus();
    slideToggle(consoleNode);

    form.addEventListener("submit", e => {
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
        command.value = "";
      });
    });

    command.addEventListener("keydown", function(e) {
      if (e.key == 'l' && e.ctrlKey) {
        output.innerText = '--- screen cleared ---';
        return false;
      } else if (e.charCode == 0 && (e.keyCode == 38 || e.keyCode == 40)) {
        // Handle up arrow and down arrow.
        if (e.keyCode == 38 && historyPos > 0) {
          historyPos--;
        } else if (e.keyCode == 40 && historyPos < history.length) {
          historyPos++;
        }
        command.value = history[historyPos];
        return false;
      }
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
        elements[i].classList.remove("nojavascript")
    }
}

function addConsoleIconToFrames(frames) {
    let consoleNode = null;
    for (let i = 0; i < frames.length; i++) {
        const target = frames[i];
        const frameID = frames[i].id.substring(6);
        target.addEventListener('click', () => {
            target.getElementsByTagName("pre")[i].parentElement.classList.toggle("expanded");
        });

        for (let j = 0; j < target.getElementsByTagName("pre").length; j++) {
            const img = createIconForConsole();
            img.addEventListener('click', (e) => {
                e.stopPropagation();
                consoleNode = openShell(consoleNode, target, frameID);
                return false;
            });
            target.getElementsByTagName("pre")[j].append(img);
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
  const consoleNode = document.createElement('pre');
  consoleNode.classList.add("console");
  consoleNode.classList.add("active");
  return consoleNode;
}

function createConsoleOutput() {
  const output = document.createElement('div');
  output.classList.add('output');
  output.innerHTML = '[console ready]';
  return output;
}

function createConsoleInputForm() {
  const form = document.createElement('form');
  form.innerHTML = '&gt;&gt;&gt; ';
  return form;
}

function createConsoleInput() {
  const command = document.createElement("input");
  command.type = "text";
  command.setAttribute("autocomplete", "off");
  command.setAttribute("spellcheck", false);
  command.setAttribute("autocapitalize", "off");
  command.setAttribute("autocorrect", "off");
  return command;
}

function createIconForConsole() {
  let img = document.createElement('img');
  img.setAttribute("src", "?__debugger__=yes&cmd=resource&f=console.png");
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
    let http = new XMLHttpRequest();
    let path = "";
    let params = {
      __debugger__: 'yes',
      cmd: encodeURIComponent(cmd),
      frm: encodeURIComponent(frameID),
      s: encodeURIComponent(SECRET)
    };
    let paramString = "&__debugger__=" + params.__debugger__ + "&cmd=" + params.cmd + "&frm=" + params.frm + "&s=" + params.s;

    http.open("GET", path + "?" + paramString, true);
    http.onreadystatechange = function() {
      if (http.readyState == 4 && http.status == 200) {
        let data = http.responseText;
        let tmp = document.createElement('div');
        tmp.innerHTML = data;
        resolve(tmp);
        $('span.extended', tmp).each(function() {
          var hidden = $(this).wrap('<span>').hide();
          hidden
            .parent()
            .append($('<a href="#" class="toggle">&nbsp;&nbsp;</a>')
              .click(function() {
                hidden.toggle();
                $(this).toggleClass('open')
                return false;
              }));
        });
      }
    };
    http.send(null);
    return false;
  });
}

function docReady(fn) {
  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(fn, 1);
  } else {
    document.addEventListener("DOMContentLoaded", fn);
  }
}
