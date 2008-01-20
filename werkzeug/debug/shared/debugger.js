HISTORY = {};
HISTORY_POSITIONS = {};

function changeTB() {
  $('#interactive').slideToggle('fast');
  $('#plain').slideToggle('fast');
}

function toggleFrameVars(num) {
  $('#frame-' + num + ' .vars').slideToggle('fast');
}

function toggleInterpreter(num) {
  $('#frame-' + num + ' .exec_code').slideToggle('fast', function() {
    if ($(this).css('display') == 'block')
      $('input.input', this).focus();
  });
}

function toggleTableVars(num) {
  $('#tvar-' + num + ' .vars').slideToggle('fast');
}

function getHistory(tb, frame) {
  var key = tb + '||' + frame;
  if (key in HISTORY)
    var h = HISTORY[key];
  else {
    var h = HISTORY[key] = [''];
    HISTORY_POSITIONS[key] = 0;
  }
  return {
    history:  h,
    setPos: function(val) {
      HISTORY_POSITIONS[key] = val;
    },
    getPos: function() {
      return HISTORY_POSITIONS[key];
    },
    getCurrent: function() {
      return h[HISTORY_POSITIONS[key]];
    }
  };
}

function addToHistory(tb, frame, value) {
  var h = getHistory(tb, frame);
  var tmp = h.history.pop();
  h.history.push(value);
  if (tmp != undefined)
    h.history.push(tmp);
  h.setPos(h.history.length - 1);
}

function backInHistory(tb, frame, input) {
  var pos, h = getHistory(tb, frame);
  if ((pos = h.getPos()) > 0)
    h.setPos(pos - 1);
  input.value = h.getCurrent();
}

function forwardInHistory(tb, frame, input) {
  var pos, h = getHistory(tb, frame);
  if ((pos = h.getPos()) < h.history.length - 1)
    h.setPos(pos + 1);
  input.value = h.getCurrent();
}

function sendCommand(tb, frame, cmd, output) {
  addToHistory(tb, frame, cmd);
  $.get('__traceback__', {
    tb:     tb,
    frame:  frame,
    code:   cmd + '\n'
  }, function(data) {
    var x = output.append($('<div>').text(data))[0];
    x.scrollTop = x.scrollHeight;
  });
}

function pasteIt() {
  var info = $('#plain p.pastebininfo');
  var orig = info.html();
  info.html('<em>submitting traceback...</em>');

  $.ajax({
    type:     'POST',
    url:      '__traceback__?pastetb=yes',
    data:     $('#plain pre.plain').text(),
    dataType: 'json',
    error: function() {
      alert('Submitting paste failed. Make sure you have a\n' +
            'working internet connection.');
      info.html(orig);
    },
    success: function(result) {
      info.text('Submitted paste: ').append(
        $('<a>').attr('href', result.url).text('#' + result.paste_id)
      );
    }
  });
}

$(document).ready(function() {
  $('.exec_code').hide();
  $('.vars').hide();
  $('.code .pre').hide();
  $('.code .post').hide();

  $('.exec_code').submit(function() {
    sendCommand(this.tb.value, this.frame.value, this.cmd.value,
                $('.output', this));
    this.cmd.value = '';
    return false;
  });

  $('.code').click(function() {
    $('.pre', $(this)).toggle();
    $('.post', $(this)).toggle();
  });

  $('.exec_code input.input').keypress(function(e) {
    if (e.charCode == 100 && e.ctrlKey) {
      $('.output', $(this).parent()).text('--- screen cleared ---');
      return false;
    }
    else if (e.charCode == 0 && (e.keyCode == 38 || e.keyCode == 40)) {
      var parent = $(this).parent();
      var tb = $('input[@name="tb"]', parent).attr('value');
      var frame = $('input[@name="frame"]', parent).attr('value');
      if (e.keyCode == 38)
        backInHistory(tb, frame, this);
      else
        forwardInHistory(tb, frame, this);
      return false;
    }
    return true;
  });
});
