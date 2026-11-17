#!/usr/bin/env node
/**
 * Arnés local de carga para TC-08 (RF-7, RNF-R-1 y RNF-R-2).
 * No admite destinos fuera del equipo local ni imprime cookies o parámetros de URL.
 */

import { setTimeout as esperar } from 'node:timers/promises'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { performance } from 'node:perf_hooks'

const USUARIOS_VIRTUALES = 70
const INTERVALO_USUARIO_MS = 6_500
const ESPACIADO_INICIAL_MS = 100
const DURACION_TC08_SEGUNDOS = 300
const UMBRAL_P95_MS = 2_000
const UMBRAL_SOLICITUDES_SEGUNDO = 10
const TIEMPO_LIMITE_SOLICITUD_MS = 10_000

export function validarDestinoLocal(valor) {
  let url
  try {
    url = new URL(valor)
  } catch {
    throw new Error('SART_URL_OBJETIVO debe ser una URL válida.')
  }

  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('SART_URL_OBJETIVO debe usar HTTP o HTTPS.')
  }
  if (url.hostname !== '127.0.0.1' && url.hostname !== '[::1]') {
    throw new Error('Por seguridad, la prueba solo admite destinos locales (127.0.0.1 o [::1]).')
  }
  if (url.username || url.password) {
    throw new Error('No incluyas credenciales en la URL objetivo.')
  }
  return url
}

export function percentil95(valores) {
  if (valores.length === 0) return null
  const ordenados = [...valores].sort((a, b) => a - b)
  return ordenados[Math.ceil(ordenados.length * 0.95) - 1]
}

export function validarCookies(cookies) {
  if (cookies.length !== USUARIOS_VIRTUALES) {
    throw new Error(`Se requieren ${USUARIOS_VIRTUALES} cookies de sesión para simular usuarios distintos.`)
  }
  if (cookies.some((cookie) => !/^sart_sesion=[A-Za-z0-9._~-]+$/.test(cookie))) {
    throw new Error('Cada entrada debe ser una cookie sart_sesion válida, sin otros atributos.')
  }
  if (new Set(cookies).size !== USUARIOS_VIRTUALES) {
    throw new Error('Las 70 cookies deben corresponder a sesiones distintas.')
  }
  return cookies
}

async function configuracion() {
  const objetivo = validarDestinoLocal(process.env.SART_URL_OBJETIVO ?? '')
  const duracion = Number(process.env.SART_DURACION_SEGUNDOS ?? DURACION_TC08_SEGUNDOS)
  if (!Number.isInteger(duracion) || duracion < 1 || duracion > DURACION_TC08_SEGUNDOS) {
    throw new Error(`SART_DURACION_SEGUNDOS debe ser un entero entre 1 y ${DURACION_TC08_SEGUNDOS}.`)
  }

  const archivoCookies = process.env.SART_COOKIES_ARCHIVO
  const cookie = process.env.SART_COOKIE ?? ''
  if (archivoCookies && cookie) {
    throw new Error('Usa SART_COOKIES_ARCHIVO o SART_COOKIE, pero no ambos.')
  }
  if (/[\r\n]/.test(cookie)) {
    throw new Error('SART_COOKIE no puede contener saltos de línea.')
  }

  if (archivoCookies) {
    const contenido = await readFile(resolve(archivoCookies), 'utf8')
    const cookies = contenido.split(/\r?\n/).map((linea) => linea.trim()).filter(Boolean)
    return { objetivo, duracion, cookies: validarCookies(cookies), sesionesUnicas: true }
  }
  if (cookie && !/^sart_sesion=[A-Za-z0-9._~-]+$/.test(cookie)) {
    throw new Error('SART_COOKIE debe contener solo la cookie sart_sesion.')
  }
  return {
    objetivo,
    duracion,
    cookies: Array(USUARIOS_VIRTUALES).fill(cookie),
    sesionesUnicas: false,
  }
}

async function cargarUsuario(objetivo, cookie, indice, inicio, fin, resultados) {
  const inicioUsuario = inicio + indice * ESPACIADO_INICIAL_MS
  if (inicioUsuario >= fin) return
  await esperar(Math.max(0, inicioUsuario - performance.now()))

  let proximaSolicitud = inicioUsuario
  while (performance.now() < fin) {
    const partida = performance.now()
    const opciones = { signal: AbortSignal.timeout(TIEMPO_LIMITE_SOLICITUD_MS) }
    if (cookie) opciones.headers = { Cookie: cookie }

    try {
      const respuesta = await fetch(objetivo, opciones)
      const latencia = performance.now() - partida
      if (performance.now() <= fin) {
        resultados.latencias.push(latencia)
        if (respuesta.ok) resultados.exitosas += 1
        else {
          resultados.fallidas += 1
          resultados.errores.push(`HTTP ${respuesta.status}`)
        }
      }
    } catch (error) {
      if (performance.now() <= fin) {
        resultados.latencias.push(performance.now() - partida)
        resultados.fallidas += 1
        resultados.errores.push(error instanceof Error ? error.name : 'Error')
      }
    }

    proximaSolicitud += INTERVALO_USUARIO_MS
    const ahora = performance.now()
    if (proximaSolicitud < ahora) proximaSolicitud = ahora + INTERVALO_USUARIO_MS
    const tiempoHastaProxima = proximaSolicitud - performance.now()
    const tiempoRestante = fin - performance.now()
    if (tiempoRestante > 0) await esperar(Math.min(tiempoHastaProxima, tiempoRestante))
  }
}

export async function ejecutarCarga({ objetivo, cookies, sesionesUnicas, duracion }) {
  const inicio = performance.now()
  const fin = inicio + duracion * 1_000
  const resultados = { latencias: [], exitosas: 0, fallidas: 0, errores: [] }

  await Promise.all(
    Array.from({ length: USUARIOS_VIRTUALES }, (_, indice) =>
      cargarUsuario(objetivo, cookies[indice], indice, inicio, fin, resultados),
    ),
  )

  const p95 = percentil95(resultados.latencias)
  const solicitudesPorSegundo = resultados.exitosas / duracion
  const cumpleMetricas =
    resultados.fallidas === 0 &&
    p95 !== null &&
    p95 <= UMBRAL_P95_MS &&
    solicitudesPorSegundo >= UMBRAL_SOLICITUDES_SEGUNDO
  const corridaCompleta = duracion === DURACION_TC08_SEGUNDOS

  console.log(`Destino local: ${objetivo.origin}`)
  console.log(`Duración: ${duracion} s${corridaCompleta ? '' : ' (preliminar)'}`)
  console.log(`Usuarios virtuales: ${USUARIOS_VIRTUALES}`)
  const autenticacion = sesionesUnicas
    ? '70 sesiones únicas'
    : cookies[0] ? 'sesión compartida entre usuarios virtuales' : 'sin cookie configurada'
  console.log(`Autenticación: ${autenticacion}`)
  console.log(`Solicitudes exitosas: ${resultados.exitosas}`)
  console.log(`Solicitudes fallidas: ${resultados.fallidas}`)
  if (resultados.errores.length > 0) {
    const resumenErrores = Object.groupBy(resultados.errores, (error) => error)
    const errores = Object.entries(resumenErrores)
      .map(([error, ocurrencias]) => `${error} (${ocurrencias.length})`)
      .join(', ')
    console.log(`Errores: ${errores}`)
  }
  console.log(`Solicitudes exitosas por segundo: ${solicitudesPorSegundo.toFixed(2)} (mínimo ${UMBRAL_SOLICITUDES_SEGUNDO})`)
  console.log(`Latencia p95: ${p95 === null ? 'sin datos' : `${p95.toFixed(0)} ms`} (máximo ${UMBRAL_P95_MS} ms)`)

  if (cumpleMetricas && corridaCompleta) {
    console.log('Resultado: carga del endpoint cumple las métricas de TC-08; Lighthouse móvil sigue pendiente.')
  } else if (cumpleMetricas) {
    console.log('Resultado: línea base preliminar; la ejecución de 5 minutos aún está pendiente.')
  } else {
    console.log('Resultado: no cumple las métricas de rendimiento de TC-08.')
  }

  return { cumpleMetricas, corridaCompleta, ...resultados, p95, solicitudesPorSegundo }
}

async function principal() {
  try {
    const resultado = await ejecutarCarga(await configuracion())
    if (!resultado.cumpleMetricas) process.exitCode = 1
  } catch (error) {
    console.error(`No se pudo ejecutar la prueba TC-08: ${error.message}`)
    process.exitCode = 1
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await principal()
}
