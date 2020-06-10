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
  addCommentToFrames(document.querySelectorAll("div.traceback div.frame"));
  toggleTraceOnClick(document.querySelectorAll('h2.traceback'));
  addNoJSPrompt(document.querySelectorAll("span.nojavascript"));

  // if we have javascript we submit by ajax anyways, so no need for the
  // not scaling textarea.
  var plainTraceback = $('div.plain textarea');
  plainTraceback.replaceWith($('<pre>').text(plainTraceback.text()));
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
    consoleNode = document.createElement('pre');
    target.parentNode.appendChild(consoleNode);
    consoleNode.classList.add("console");
    consoleNode.classList.add("active");
    var historyPos = 0,
        history = [''];

    var output = document.createElement('div');
    output.classList.add('output');
    output.innerHTML = '[console ready]';
    consoleNode.append(output);

    var form = document.createElement('form');
    form.innerHTML = '&gt;&gt;&gt; ';
    consoleNode.append(form);

    form.addEventListener("submit", function(e) {
        e.preventDefault();
        console.log("submitting");
        var cmd = command.value;
        $.get('', {
            __debugger__: 'yes',
            cmd: cmd,
            frm: frameID,
            s: SECRET
        }, function(data) {
            // var tmp = $('<div>').html(data);
            var tmp = document.createElement('div');
            tmp.innerHTML = data;

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
            output.append(tmp);
            command.focus();
            consoleNode.scrollTo(0, consoleNode.scrollHeight);
            var old = history.pop();
            history.push(cmd);
            if (typeof old != 'undefined') {
                history.push(old);
            }
            historyPos = history.length - 1;
        });
        command.value = "";
        return false;
    });

    var command = document.createElement("input");
    command.type = "text";
    command.setAttribute("autocomplete", "off");
    command.setAttribute("spellcheck", false);
    command.setAttribute("autocapitalize", "off");
    command.setAttribute("autocorrect", "off");
    command.addEventListener("keydown", function(e) {
        if (e.key == 'l' && e.ctrlKey) {
            output.innerText = '--- screen cleared ---';
            return false;
        } else if (e.charCode == 0 && (e.keyCode == 38 || e.keyCode == 40)) {
            //   handle up arrow and down arrow
            if (e.keyCode == 38 && historyPos > 0) {
                historyPos--;
            } else if (e.keyCode == 40 && historyPos < history.length) {
                historyPos++;
            }
            // command.val(history[historyPos]);
            command.value = history[historyPos];
            return false;
        }
    });
    form.append(command);
    command.focus();
    slideToggle(consoleNode);

    return consoleNode;
}

function addEventListenersToElements(elements, typeOfEvent, typeOfListener) {
    for (let i = 0; i < elements.length; i++) {
        elements[i].addEventListener(typeOfEvent, typeOfListener);
    }
}

function emptyChildClasses(elements) {
    console.log("emptyChildClasses() called successfully")
    console.log("Before loop " + elements)

    while (elements.firstChild) { // not being entered because elements is already empty, so elements.firstChild returns false
        elements.removeChild(firstChild);
        console.log("Removed a child class successfully")
    }

    console.log("After loop " + elements)
    return elements
}

/**
 * Add extra info (this is here so that only users with JavaScript
 * enabled see it.)
 */
function addNoJSPrompt(elements) {

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

function addCommentToFrames(frames) {
    let consoleNode = null;
    for (let i = 0; i < frames.length; i++) {
      const target = frames[i];
      const frameID = frames[i].id.substring(6);
      target.addEventListener('click', () => {
        console.log("dont!");
        target.getElementsByTagName("pre")[i].parentElement.classList.toggle("expanded");
      });

      /**
       * Add an interactive console to the frames
       */
      for (let j = 0; j < target.getElementsByTagName("pre").length; j++) {
        let img = document.createElement('img');
        img.setAttribute("src", "?__debugger__=yes&cmd=resource&f=console.png");
        img.setAttribute('title', 'Open an interactive python shell in this frame');
        img.addEventListener('click', (e) => {
          e.stopPropagation();
          console.log('consoleNOde', consoleNode);
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
function toggleTraceOnClick(elements) {
  for (let i = 0; i < elements.length; i++) {
    elements[i].addEventListener('click', () => {
      $(this).next().slideToggle('fast');
      $('div.plain').slideToggle('fast');
    });
    elements[i].style.cursor = 'pointer';
    document.querySelector('div.plain').style.display = 'none';
  }
}

function docReady(fn) {
  // see if DOM is already available
  if (document.readyState === "complete" || document.readyState === "interactive") {
    // call on next available tick
    setTimeout(fn, 1);
  } else {
    document.addEventListener("DOMContentLoaded", fn);
  }
}
