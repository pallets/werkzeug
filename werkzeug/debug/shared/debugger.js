$(function() {
  $('div.traceback div.frame').each(function() {
    var target = $('pre', this), frameConsole = null, table = null, source = null,
        frameID = this.id.substring(6);

    //
    // Add an interactive console
    //
    var consoleBtn = $('<img src="./__debugger__?resource=console.png">')
      .attr('title', 'Open an interactive python shell in this frame')
      .click(function() {
        if (!frameConsole) {
          frameConsole = $('<pre class="console">')
            .appendTo(target.parent())
            .hide()
          var output = $('<div class="output">[console ready]</div>')
            .appendTo(frameConsole);
          var form = $('<form>&gt;&gt;&gt; </form>')
            .submit(function() {
              var cmd = command.val();
              $.get('./__debugger__', {cmd: cmd, frame: frameID}, function(data) {
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
              });
              command.val('');
              return false;
            }).
            appendTo(frameConsole);
          var command = $('<input type="text">').appendTo(form);
          frameConsole.slideDown('fast', function() {
            command.focus();
          });
        }
        else
          frameConsole.slideToggle('fast');
      })
      .prependTo(target);

    //
    // Display local variables
    //
    $('<img src="./__debugger__?resource=inspect.png">')
      .attr('title', 'Show table of local variables')
      .click(function() {
        var console = $('pre.console', $(this).parent().parent());
        if (!console.is(':visible'))
          consoleBtn.click();
        var form = $('form', console);
        $('input', form).val('dump()');
        form.submit();
      })
      .prependTo(target);

    //
    // Show Sourcecode
    //
    $('<img src="./__debugger__?resource=source.png">')
      .attr('title', 'Display the sourcecode for this frame')
      .click(function() {

      })
      .prependTo(target);
  });

  //
  // Toggle the traceback types on click.
  //
  $('h2.traceback').click(function() {
    $(this).next().slideToggle('fast');
    $('div.plain').slideToggle('fast');
  }).css('cursor', 'pointer');
  $('div.plain').hide();

  //
  // Now add extra info (this is here so that only users with JavaScript
  // enabled see it.)
  //
  $('span.nojavascript')
    .removeClass('nojavascript')
    .text('To switch between the interactive traceback and the plaintext ' +
          'one, you can click on the "Traceback" headline.  From the text ' +
          'traceback you can also create a paste of it.  For code execution ' +
          'mouse-over the frame you want to debug and click on the console ' +
          'icon on the right side.');
});
