// Logo de SART (diseño de Figma): cuadro con una línea de pulso, nombre y lema.

export function IconoPulso({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="2 12 6 12 9 4 13 20 16 9 18 12 22 12" />
    </svg>
  )
}

export function Logo() {
  return (
    <div className="logo">
      <span className="logo__cuadro"><IconoPulso className="logo__pulso" /></span>
      <span className="logo__textos">
        <span className="logo__nombre">SART</span>
        <span className="logo__lema">Alerta respiratoria temprana</span>
      </span>
    </div>
  )
}
