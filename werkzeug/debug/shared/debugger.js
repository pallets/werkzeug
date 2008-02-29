$(function() {
  var sourceView = null;
  $('div.traceback div.frame').each(function() {
    var target = $('pre', this), frameConsole = null, table = null,
        source = null, frameID = this.id.substring(6);

    /**
     * Add an interactive console
     */
    var consoleBtn = $('<img src="./__debugger__?cmd=resource&f=console.png">')
      .attr('title', 'Open an interactive python shell in this frame')
      .click(function() {
        if (!frameConsole) {
          frameConsole = $('<pre class="console">')
            .appendTo(target.parent())
            .hide()
          var historyPos = 0, history = [''];
          var output = $('<div class="output">[console ready]</div>')
            .appendTo(frameConsole);
          var form = $('<form>&gt;&gt;&gt; </form>')
            .submit(function() {
              var cmd = command.val();
              $.get('./__debugger__', {cmd: cmd, frm: frameID}, function(data) {
                var tmp = $('<div>').html(data);
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
                var old = history.pop();
                history.push(cmd);
                if (typeof old != 'undefined')
                  history.push(old);
                historyPos = history.length - 1;
              });
              command.val('');
              return false;
            }).
            appendTo(frameConsole);
          var command = $('<input type="text">')
            .appendTo(form)
            .keypress(function(e) {
              if (e.charCode == 100 && e.ctrlKey) {
                output.text('--- screen cleared ---');
                return false;
              }
              else if (e.charCode == 0 && (e.keyCode == 38 || e.keyCode == 40)) {
                if (e.keyCode == 38 && historyPos > 0)
                  historyPos--;
                else if (e.keyCode == 40 && historyPos < history.length)
                  historyPos++;
                command.val(history[historyPos]);
                return false;
              }
            });
            
          frameConsole.slideDown('fast', function() {
            command.focus();
          });
        }
        else
          frameConsole.slideToggle('fast');
      })
      .prependTo(target);

    /**
     * Show sourcecode
     */
    $('<img src="./__debugger__?cmd=resource&f=source.png">')
      .attr('title', 'Display the sourcecode for this frame')
      .click(function() {
        if (!sourceView)
          $('h2', sourceView =
            $('<div class="box"><h2>View Source</h2><table>')
              .insertBefore('div.explanation'))
            .css('cursor', 'pointer')
            .click(function() {
              sourceView.slideUp('fast');
            });
        $.get('./__debugger__', {cmd: 'source', frm: frameID}, function(data) {
          $('table', sourceView)
            .replaceWith(data);
          if (!sourceView.is(':visible'))
            sourceView.slideDown('fast', function() {
              document.location.href = '#current-line';
            });
          else
            document.location.href = '#current-line';
        });
      })
      .prependTo(target);
  });

  /**
   * toggle traceback types on click.
   */
  $('h2.traceback').click(function() {
    $(this).next().slideToggle('fast');
    $('div.plain').slideToggle('fast');
  }).css('cursor', 'pointer');
  $('div.plain').hide();

  /**
   * Add extra info (this is here so that only users with JavaScript
   * enabled see it.)
   */
  $('span.nojavascript')
    .removeClass('nojavascript')
    .text('To switch between the interactive traceback and the plaintext ' +
          'one, you can click on the "Traceback" headline.  From the text ' +
          'traceback you can also create a paste of it.  For code execution ' +
          'mouse-over the frame you want to debug and click on the console ' +
          'icon on the right side.');
});


/**
 * Helper function to dump the plaintext traceback into the lodgeit
 * pastebin.
 */
function dumpThis() {
  $.ajax({
    dataType:     'json',
    url:          './__debugger__',
    data:         {tb: TRACEBACK, cmd: 'paste'},
    success:      function(data) {
      console.log(data);
      $('div.plain span.pastemessage')
        .removeClass('pastemessage')
        .text('Paste created: ')
        .append($('<a>#' + data.id + '</a>').attr('href', data.url));
  }});
};
