import { TextField, InputAdornment, Alert, CircularProgress } from "@mui/material";
import PersonIcon from '@mui/icons-material/Person';
import LockIcon from '@mui/icons-material/Lock';
import "./css/LoginScreen.scss"
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";

import { useAuth } from "../context/authContext.tsx";
import { ErrorInicioSesion, iniciarSesion } from "../services/authService.ts";

// Adaptado de ing-software2. La autenticación real (Argon2id, cookie JWT, MFA) es la actividad 8.
export function LoginScreen() {
    const { login, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const destino = (location.state as { desde?: string } | null)?.desde ?? "/centros";

    const [correo, setCorreo] = useState("");
    const [contrasena, setContrasena] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (isAuthenticated) return <Navigate to={destino} replace />;

    const onSubmit = async (evento: FormEvent) => {
        evento.preventDefault();
        if (!correo || !contrasena) {
            setError("Por favor, ingrese todos los campos.");
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            const usuario = await iniciarSesion(correo, contrasena);
            login(usuario);
            navigate(destino, { replace: true });
        } catch (err) {
            setError(err instanceof ErrorInicioSesion ? err.message : "Error inesperado. Intente nuevamente.");
        } finally {
            setIsLoading(false);
        }
    }

    return (
        <section className="login">
            <div className="login__top">
                <h1 className="login__titulo">SART</h1>
                <p className="login__subtitulo">Sistema de Alerta Respiratoria Temprana · Gran Concepción</p>
            </div>
            <form className="login__main" onSubmit={onSubmit} noValidate>
                <p>Ingrese sus datos de usuario.</p>
                {error && (
                    <Alert severity="error" className="login-alert">
                        {error}
                    </Alert>
                )}
                <TextField
                    required
                    className="username-input"
                    label="Correo institucional"
                    type="email"
                    autoComplete="username"
                    variant="outlined"
                    value={correo}
                    onChange={(e) => setCorreo(e.target.value)}
                    slotProps={{
                        input: {
                            startAdornment: (
                                <InputAdornment position="start">
                                    <PersonIcon />
                                </InputAdornment>
                            ),
                        }
                    }}
                />
                <TextField
                    required
                    className="password-input"
                    label="Contraseña"
                    type="password"
                    autoComplete="current-password"
                    variant="outlined"
                    value={contrasena}
                    onChange={(e) => setContrasena(e.target.value)}
                    slotProps={{
                        input: {
                            startAdornment: (
                                <InputAdornment position="start">
                                    <LockIcon />
                                </InputAdornment>
                            ),
                        }
                    }}
                />
                <button type="submit" className="login-button" disabled={isLoading}>
                    {isLoading ? <CircularProgress size={20} color="inherit" sx={{ mr: 1 }} /> : null}
                    {isLoading ? "Cargando..." : "Iniciar sesión"}
                </button>
            </form>
        </section>
    )
}
