import ArrowBackOutlinedIcon from '@mui/icons-material/ArrowBackOutlined';
import ArrowForwardOutlinedIcon from '@mui/icons-material/ArrowForwardOutlined';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import MailOutlineIcon from '@mui/icons-material/MailOutlined';
import PhonelinkLockOutlinedIcon from '@mui/icons-material/PhonelinkLockOutlined';
import VisibilityOffOutlinedIcon from '@mui/icons-material/VisibilityOffOutlined';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import "./css/InicioSesion.scss";

import { destinoTrasLogin } from "../acceso/rutas.ts";
import { Logo } from "../componentes/Logo.tsx";
import { AvisoEntorno } from "../componentes/PiePagina.tsx";
import { useSesion } from "../contexto/sesion.tsx";
import { ErrorInicioSesion, iniciarSesion } from "../servicios/sesion.ts";

// Gráfico decorativo del panel izquierdo (diseño de Figma): serie observada y tramo de pronóstico punteado.
function GraficoPortada() {
    return (
        <figure className="portada__grafico" aria-hidden="true">
            <svg viewBox="0 0 400 130" preserveAspectRatio="none">
                <line x1="0" y1="12" x2="400" y2="12" />
                <line x1="0" y1="52" x2="400" y2="52" />
                <line x1="0" y1="92" x2="400" y2="92" />
                <polyline className="portada__observado"
                    points="0,127 40,112 80,119 120,81 160,91 200,49 240,57 280,24 320,42 360,0 400,15" />
                <polyline className="portada__pronostico" points="312,56 400,0" />
            </svg>
            <figcaption>
                <span>Vigilancia</span><span>Pronóstico</span><span>Acción</span>
            </figcaption>
        </figure>
    );
}

// Inicio de sesión (diseño «Inicio de sesión»). La API valida la clave (Argon2id) y pone la cookie JWT. Si la
// cuenta es de administrador, responde «mfa_requerido» y aquí se pide el código de la aplicación (RNF-S-1).
// Sin «¿Olvidaste tu contraseña?»: no hay requisito de recuperación (docs/pendientes_informe.md #23).
export function PantallaInicioSesion() {
    const { iniciar, autenticado, usuario } = useSesion();
    const navigate = useNavigate();
    const location = useLocation();
    const desde = (location.state as { desde?: string } | null)?.desde;

    const [correo, setCorreo] = useState("");
    const [contrasena, setContrasena] = useState("");
    const [verClave, setVerClave] = useState(false);
    const [pideCodigo, setPideCodigo] = useState(false);
    const [codigo, setCodigo] = useState("");
    const [cargando, setCargando] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (autenticado && usuario) return <Navigate to={destinoTrasLogin(usuario.rol, desde)} replace />;

    const volverAlPrimerPaso = () => {
        setPideCodigo(false);
        setCodigo("");
        setError(null);
    };

    const onSubmit = async (evento: FormEvent) => {
        evento.preventDefault();
        if (!correo || !contrasena || (pideCodigo && !codigo)) {
            setError("Por favor, complete todos los campos.");
            return;
        }
        setCargando(true);
        setError(null);
        try {
            const resultado = await iniciarSesion(correo, contrasena, pideCodigo ? codigo : undefined);
            if (resultado.tipo === "mfa_requerido") {
                setPideCodigo(true);
                return;
            }
            iniciar(resultado.usuario);
            navigate(destinoTrasLogin(resultado.usuario.rol, desde), { replace: true });
        } catch (err) {
            setCodigo("");
            setError(err instanceof ErrorInicioSesion ? err.message : "Error inesperado. Intente nuevamente.");
        } finally {
            setCargando(false);
        }
    };

    return (
        <div className="login">
            <aside className="portada">
                <Logo />
                <div className="portada__centro">
                    <p className="portada__antetitulo">Gran Concepción · Chile</p>
                    <p className="portada__lema">Anticipar la demanda. Preparar la respuesta.</p>
                    <p className="portada__descripcion">
                        Sistema de Alerta Respiratoria Temprana para equipos de urgencia y gestión de la red.
                    </p>
                    <GraficoPortada />
                </div>
                <p className="portada__pie">Herramienta de apoyo a la decisión; no reemplaza el criterio clínico</p>
            </aside>

            <main className="acceso">
                <form className="acceso__formulario" onSubmit={onSubmit} noValidate>
                    <p className="acceso__antetitulo">
                        <LockOutlinedIcon aria-hidden="true" /> Acceso institucional
                    </p>
                    <h1 className="acceso__titulo">Bienvenido a SART</h1>
                    <p className="acceso__bajada">
                        Información oportuna para anticipar la demanda de tu servicio de urgencia.
                    </p>

                    {error && <p className="acceso__error" role="alert">{error}</p>}

                    {!pideCodigo ? (
                        <>
                            <div className="campo">
                                <label htmlFor="correo">Correo institucional</label>
                                <div className="campo__caja">
                                    <input id="correo" type="email" autoComplete="username" value={correo}
                                        onChange={(e) => setCorreo(e.target.value)} placeholder="nombre@servicio.cl" />
                                    <MailOutlineIcon className="campo__icono" aria-hidden="true" />
                                </div>
                            </div>
                            <div className="campo">
                                <label htmlFor="contrasena">Contraseña</label>
                                <div className="campo__caja">
                                    <input id="contrasena" type={verClave ? "text" : "password"}
                                        autoComplete="current-password" value={contrasena}
                                        onChange={(e) => setContrasena(e.target.value)} />
                                    <button type="button" className="campo__boton-icono"
                                        aria-label={verClave ? "Ocultar contraseña" : "Mostrar contraseña"}
                                        onClick={() => setVerClave((v) => !v)}>
                                        {verClave ? <VisibilityOutlinedIcon aria-hidden="true" />
                                            : <VisibilityOffOutlinedIcon aria-hidden="true" />}
                                    </button>
                                </div>
                            </div>
                        </>
                    ) : (
                        <>
                            <p className="acceso__info">
                                Ingrese el código de 6 dígitos de su aplicación de autenticación para {correo}.
                            </p>
                            <div className="campo">
                                <label htmlFor="codigo">Código de verificación</label>
                                <div className="campo__caja">
                                    <input id="codigo" className="campo__codigo" autoFocus inputMode="numeric"
                                        autoComplete="one-time-code" maxLength={6} value={codigo}
                                        onChange={(e) => setCodigo(e.target.value.replace(/\D/g, "").slice(0, 6))} />
                                    <PhonelinkLockOutlinedIcon className="campo__icono" aria-hidden="true" />
                                </div>
                            </div>
                        </>
                    )}

                    <button type="submit" className="boton-primario acceso__enviar" disabled={cargando}>
                        {!cargando && <ArrowForwardOutlinedIcon aria-hidden="true" />}
                        {cargando ? "Verificando…" : pideCodigo ? "Verificar" : "Ingresar"}
                    </button>
                    {pideCodigo && (
                        <button type="button" className="boton-enlace" onClick={volverAlPrimerPaso}>
                            <ArrowBackOutlinedIcon aria-hidden="true" /> Usar otra cuenta
                        </button>
                    )}

                    <hr className="acceso__separador" />
                    <p className="acceso__nota">
                        Acceso solo para personal autorizado. Las cuentas son creadas por el administrador; no hay
                        registro público.
                    </p>
                    <p className="acceso__entorno"><AvisoEntorno /></p>
                </form>
            </main>
        </div>
    );
}
