/* Details start hidden in HTML and open only through their row's button. */
(function () {
  'use strict';
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.perf-toggle'));
  function setExpanded(button, expanded) {
    var row = document.getElementById(button.getAttribute('aria-controls'));
    if (!row) { return; }
    row.hidden = !expanded;
    row.classList.toggle('is-open', expanded);
    button.setAttribute('aria-expanded', String(expanded));
    button.querySelector('.perf-toggle-icon').textContent = expanded ? '-' : '+';
  }
  buttons.forEach(function (button) {
    setExpanded(button, false);
    button.disabled = false;
    button.addEventListener('click', function () {
      setExpanded(button, button.getAttribute('aria-expanded') !== 'true');
    });
  });
})();
