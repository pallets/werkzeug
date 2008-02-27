$(function() {
  $('div.traceback div.frame').each(function() {
    var target = $('pre', this), frameConsole = null, table = null, source = null,
        frameID = this.id.substring(6);
    $('<img src="./__debugger__?resource=console.png">')
      .attr('title', 'Open an interactive python shell in this frame')
      .click(function() {
        if (!frameConsole) {
          frameConsole = $('<pre class="console">')
            .appendTo(target.parent())
            .hide()
          var output = $('<div class="output">[console ready]</div>')
            .appendTo(frameConsole);
          $('<form>&gt;&gt;&gt; <input type="text" name="command"></div>')
            .submit(function() {
              var cmd = this.command.value; this.command.value = '';
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
              return false;
            })
            .appendTo(frameConsole);
        }
        frameConsole.slideToggle('fast');
      })
      .prependTo(target);
    $('<img src="./__debugger__?resource=inspect.png">')
      .attr('title', 'Show table of local variables')
      .click(function() {

      })
      .prependTo(target);
    $('<img src="./__debugger__?resource=source.png">')
      .attr('title', 'Display the sourcecode for this frame')
      .click(function() {

      })
      .prependTo(target);
  });
});
