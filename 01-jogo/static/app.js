'use strict';

document.querySelectorAll('input[type="file"]').forEach((input) => {
  let previewUrl;
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;
    if (file.type !== 'image/jpeg') {
      input.value = '';
      window.alert('Selecione uma imagem JPEG.');
      return;
    }
    const image = input.closest('figure')?.querySelector('img');
    if (image) {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = URL.createObjectURL(file);
      image.src = previewUrl;
    }
  });
});
