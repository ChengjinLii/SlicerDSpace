/* Static measurements remain readable when JavaScript is disabled. */
(function () {
  'use strict';
  var controls = document.querySelector('.perf-filters');
  if (!controls) { return; }
  controls.hidden = false;
  var buttons = controls.querySelectorAll('[data-perf-filter]');
  var items = document.querySelectorAll('[data-category]');
  var count = document.getElementById('perf-count');
  Array.prototype.forEach.call(buttons, function (button) {
    button.addEventListener('click', function () {
      var filter = button.getAttribute('data-perf-filter');
      var categories = filter.split(',');
      Array.prototype.forEach.call(buttons, function (item) { item.setAttribute('aria-pressed', String(item === button)); });
      Array.prototype.forEach.call(items, function (item) { item.hidden = filter !== 'all' && categories.indexOf(item.getAttribute('data-category')) === -1; });
      document.querySelector('.perf-chart-grid').hidden = filter !== 'all' && categories.indexOf('implementation') === -1;
      var visible = document.querySelectorAll('.perf-table tbody tr:not([hidden])').length;
      count.textContent = visible + ' measurement' + (visible === 1 ? '' : 's');
    });
  });
  function openMethod(id) {
    var item = document.getElementById(id);
    if (item && item.classList.contains('perf-method')) { item.open = true; }
  }
  Array.prototype.forEach.call(document.querySelectorAll('a[href^="#method-"]'), function (link) {
    link.addEventListener('click', function () {
      // The same fragment can be clicked again after its details were closed.
      openMethod(link.getAttribute('href').slice(1));
    });
  });
  window.addEventListener('hashchange', function () { openMethod(location.hash.slice(1)); });
  openMethod(location.hash.slice(1));
  count.textContent = document.querySelectorAll('.perf-table tbody tr').length + ' measurements';
})();
