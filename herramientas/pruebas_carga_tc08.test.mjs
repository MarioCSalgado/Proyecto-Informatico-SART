import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { percentil95, validarCookies, validarDestinoLocal } from './pruebas_carga_tc08.mjs'

describe('TC-08 · arnés de carga', () => {
  it('solo permite destinos de loopback para evitar cargar servicios externos', () => {
    assert.equal(validarDestinoLocal('http://127.0.0.1:8000/centros/estado').pathname, '/centros/estado')
    assert.throws(() => validarDestinoLocal('https://ejemplo.com/'), /solo admite destinos locales/)
    assert.throws(() => validarDestinoLocal('http://usuario:clave@127.0.0.1/'), /No incluyas credenciales/)
  })

  it('calcula p95 con rango cercano superior y admite una muestra vacía', () => {
    assert.equal(percentil95([50, 10, 40, 20, 30]), 50)
    assert.equal(percentil95([]), null)
  })

  it('exige 70 cookies de sesión distintas para una corrida completa', () => {
    const cookies = Array.from({ length: 70 }, (_, indice) => `sart_sesion=token-${indice}`)
    assert.equal(validarCookies(cookies).length, 70)
    assert.throws(() => validarCookies(cookies.slice(1)), /Se requieren 70 cookies/)
    assert.throws(() => validarCookies(Array(70).fill(cookies[0])), /sesiones distintas/)
  })
})
