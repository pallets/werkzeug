$(function() {

    if (!EVALEX_TRUSTED) {
        initPinBox();
    }

    /**
     * if we are in console mode, show the console.
     */
    if (CONSOLE_MODE && EVALEX) {
        openShell(null, $('div.console div.inner').empty(), 0);
        // openShell(null, emptyChildClasses(document.querySelectorAll('div.console div.inner')), 0); get this working
    }

    addEventListenersToElements(document.querySelectorAll("div.detail"), 'click', () => {
        document.querySelectorAll("div.traceback")[0].scrollIntoView(false);
    });

    addCommentToFrames(document.querySelectorAll("div.traceback div.frame"));


    /**
     * toggle traceback types on click.
     */
    toggleTraceOnClick(document.querySelectorAll('h2.traceback')); // incomplete, still uses jQuery in this function


    /**
     * Add extra info (this is here so that only users with JavaScript
     * enabled see it.)
     */
    addNoJSPrompt(document.querySelectorAll("span.nojavascript"))


    /**
     * Add the pastebin feature
     */
    $('div.plain form')
        .submit(function() {
            var label = $('input[type="submit"]', this);
            var old_val = label.val();
            label.val('submitting...');
            $.ajax({
                dataType: 'json',
                url: document.location.pathname,
                data: {
                    __debugger__: 'yes',
                    tb: TRACEBACK,
                    cmd: 'paste',
                    s: SECRET
                },
                success: function(data) {
                    $('div.plain span.pastemessage')
                        .removeClass('pastemessage')
                        .text('Paste created: ')
                        .append($('<a>#' + data.id + '</a>').attr('href', data.url));
                },
                error: function() {
                    alert('Error: Could not submit paste.  No network connection?');
                    label.val(old_val);
                }
            });
            return false;
        });

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

    // var output = $('<div class="output">[console ready]</div>')
    //     .appendTo(consoleNode);
    var output = document.createElement('div');
    output.classList.add('output');
    output.innerHTML = '[console ready]';
    consoleNode.appendChild(output);

    var form = $('<form>&gt;&gt;&gt; </form>')
        .submit(function() {
            var cmd = command.val();
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
                if (typeof old != 'undefined')
                    history.push(old);
                historyPos = history.length - 1;
            });
            command.val('');
            return false;
        }).
    appendTo(consoleNode);

    var command = $('<input type="text" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">')
        .appendTo(form)
        .keydown(function(e) {
            if (e.key == 'l' && e.ctrlKey) {
                output.text('--- screen cleared ---');
                return false;
            } else if (e.charCode == 0 && (e.keyCode == 38 || e.keyCode == 40)) {
                //   handle up arrow and down arrow
                if (e.keyCode == 38 && historyPos > 0)
                    historyPos--;
                else if (e.keyCode == 40 && historyPos < history.length)
                    historyPos++;
                command.val(history[historyPos]);
                return false;
            }
        });

    // return consoleNode.slideDown('fast', function() {
    command.focus();
    slideToggle(consoleNode);
    return consoleNode;
    // });
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
