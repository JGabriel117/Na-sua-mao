/* Geolocalizacao do usuario.
 *
 * Fluxo:
 *   1. Ao entrar (qualquer pagina autenticada) o navegador pergunta a permissao
 *      automaticamente, uma vez por sessao, se o usuario ainda nao tem coordenadas.
 *   2. Autorizado -> grava as coordenadas (origem "navegador") e recarrega.
 *   3. Negado / indisponivel / sem HTTPS -> cai para o CEP cadastrado (origem "cep").
 *   4. Sem CEP -> o catalogo mostra o convite para cadastrar o CEP em Meu perfil.
 */
(function () {
  var config = document.getElementById('geo-auto');
  if (!config) return;

  var formGeo = document.getElementById('form-geo-auto');
  var formCep = document.getElementById('form-cep-auto');
  var temCoords = config.dataset.temCoords === '1';
  var origem = config.dataset.origem || '';
  var cep = (config.dataset.cep || '').replace(/\D/g, '');
  var aviso = document.getElementById('msg-localizacao');

  function avisar(texto, erro) {
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.className = 'mt-2 text-xs font-medium ' + (erro ? 'text-red-600' : 'text-indigo-600');
  }

  function enviarPosicao(posicao) {
    formGeo.querySelector('[name="latitude"]').value = posicao.coords.latitude.toFixed(6);
    formGeo.querySelector('[name="longitude"]').value = posicao.coords.longitude.toFixed(6);
    formGeo.submit();
  }

  function usarCep(automatico) {
    if (!cep) {
      if (automatico) {
        avisar('Localização não autorizada. Cadastre seu CEP em Meu perfil para vermos ferramentas perto de você.', true);
      }
      return;
    }
    if (automatico && sessionStorage.getItem('nsm-cep-tentado') === '1') return;
    sessionStorage.setItem('nsm-cep-tentado', '1');
    formCep.submit();
  }

  function pedir(automatico) {
    if (!navigator.geolocation) {
      if (automatico) return usarCep(true);
      return avisar('Seu navegador não oferece geolocalização. Use o botão "Usar meu CEP".', true);
    }
    if (!window.isSecureContext) {
      if (automatico) return usarCep(true);
      return avisar('Não conseguimos usar a localização neste navegador. Vamos usar seu CEP.', true);
    }

    if (!automatico) avisar('Obtendo sua localização...');

    navigator.geolocation.getCurrentPosition(
      enviarPosicao,
      function (erro) {
        if (automatico) return usarCep(true);
        var mensagens = {
          1: 'Permissão de localização negada. Use o CEP cadastrado ou libere a localização no navegador.',
          2: 'Não foi possível determinar sua posição agora. Tente novamente ou use o CEP.',
          3: 'A localização demorou demais para responder. Tente novamente ou use o CEP.'
        };
        avisar(mensagens[erro.code] || 'Não foi possível obter sua localização.', true);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 600000 }
    );
  }

  window.NSMGeo = { pedir: pedir, usarCep: usarCep };

  var botaoLocalizacao = document.getElementById('btn-localizacao');
  if (botaoLocalizacao) {
    botaoLocalizacao.addEventListener('click', function () {
      sessionStorage.removeItem('nsm-cep-tentado');
      pedir(false);
    });
  }

  var botaoCep = document.getElementById('btn-cep');
  if (botaoCep) {
    botaoCep.addEventListener('click', function () {
      sessionStorage.removeItem('nsm-cep-tentado');
      usarCep(false);
    });
  }

  // ---- Entrada ----
  if (!temCoords) {
    if (sessionStorage.getItem('nsm-geo-tentado') === '1') return;
    sessionStorage.setItem('nsm-geo-tentado', '1');
    if (!navigator.permissions || !navigator.permissions.query) return pedir(true);
    navigator.permissions.query({ name: 'geolocation' }).then(function (status) {
      // "denied": nao insiste no prompt, vai direto ao CEP.
      if (status.state === 'denied') usarCep(true);
      else pedir(true);
    }).catch(function () { pedir(true); });
    return;
  }

  // Localizacao estimada por CEP: refina com o navegador se a permissao ja existe.
  if (origem === 'cep' && navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: 'geolocation' }).then(function (status) {
      if (status.state === 'granted') pedir(true);
    }).catch(function () {});
  }
})();
