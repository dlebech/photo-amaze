(($) => {
  const setupForm = () => {
    $('form').submit(function () {
      $(this).find('button[type="submit"]').button('loading');
    });
  };

  const setFormStatus = () => {
    if (!window.formStatus) return;

    Object.keys(window.formStatus.error).forEach((name) => {
      $(`input[name="${name}"]`)
        .prop('title', window.formStatus.error[name])
        .parent().addClass('has-error');
    });
  };

  $(document).ready(() => {
    // Set the form status.
    setFormStatus();

    // Setup tooltips
    $('[title]').tooltip();

    // Set button toggles.
    setupForm();
  });
})(window.jQuery);
