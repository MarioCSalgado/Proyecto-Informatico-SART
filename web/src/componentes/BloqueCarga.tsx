type Props = {
  ancho?: string
  alto?: string
  radio?: string
}

/** Bloque gris animado que ocupa el lugar de un contenido mientras carga. */
export function BloqueCarga({ ancho = '100%', alto = '1rem', radio = '6px' }: Props) {
  return (
    <div className="bloque-carga" style={{ width: ancho, height: alto, borderRadius: radio }} aria-hidden="true" />
  )
}
