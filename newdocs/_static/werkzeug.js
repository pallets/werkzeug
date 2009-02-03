(function() {
  Werkzeug = {};

  $(function() {
    $('#toc h3').click(function() {
      $(this).next().slideToggle();
      $(this).parent().toggleClass('toc-collapsed');
    }).next().hide().parent().addClass('toc-collapsed');
  });
})();
