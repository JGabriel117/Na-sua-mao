/* Carrossel leve para os anuncios (ate 5 fotos), sem dependencias externas.
 *
 * Estrutura esperada:
 *   <div data-carrossel>
 *     <img data-slide ...>            (um ou mais slides)
 *     <button data-prev>...</button>
 *     <button data-next>...</button>
 *     <span data-contador>1 / 3</span>
 *     <button data-ir="0">...</button>  (miniaturas ou bolinhas)
 *   </div>
 */
(function () {
  function iniciar(raiz) {
    var slides = Array.prototype.slice.call(raiz.querySelectorAll('[data-slide]'));
    if (slides.length < 2) return;

    var atual = 0;
    var contador = raiz.querySelector('[data-contador]');
    var alvos = Array.prototype.slice.call(raiz.querySelectorAll('[data-ir]'));

    function mostrar(indice) {
      atual = (indice + slides.length) % slides.length;
      slides.forEach(function (slide, i) {
        slide.classList.toggle('hidden', i !== atual);
      });
      alvos.forEach(function (alvo, i) {
        alvo.classList.toggle('border-indigo-500', i === atual);
        alvo.classList.toggle('border-transparent', i !== atual);
        alvo.classList.toggle('border-gray-100', i !== atual);
        alvo.classList.toggle('opacity-60', i !== atual);
      });
      if (contador) contador.textContent = (atual + 1) + ' / ' + slides.length;
    }

    raiz.querySelectorAll('[data-prev]').forEach(function (botao) {
      botao.addEventListener('click', function (evento) {
        evento.preventDefault();
        mostrar(atual - 1);
      });
    });

    raiz.querySelectorAll('[data-next]').forEach(function (botao) {
      botao.addEventListener('click', function (evento) {
        evento.preventDefault();
        mostrar(atual + 1);
      });
    });

    alvos.forEach(function (alvo, i) {
      alvo.addEventListener('click', function (evento) {
        evento.preventDefault();
        mostrar(i);
      });
    });

    // Navegacao por teclado quando o carrossel esta em foco
    raiz.setAttribute('tabindex', '0');
    raiz.addEventListener('keydown', function (evento) {
      if (evento.key === 'ArrowLeft') mostrar(atual - 1);
      if (evento.key === 'ArrowRight') mostrar(atual + 1);
    });

    // Deslizar no celular
    var inicioX = null;
    raiz.addEventListener('touchstart', function (evento) {
      inicioX = evento.touches[0].clientX;
    }, { passive: true });
    raiz.addEventListener('touchend', function (evento) {
      if (inicioX === null) return;
      var delta = evento.changedTouches[0].clientX - inicioX;
      if (Math.abs(delta) > 40) mostrar(atual + (delta < 0 ? 1 : -1));
      inicioX = null;
    }, { passive: true });

    mostrar(0);
  }

  function iniciarTodos() {
    document.querySelectorAll('[data-carrossel]').forEach(iniciar);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciarTodos);
  } else {
    iniciarTodos();
  }
})();
