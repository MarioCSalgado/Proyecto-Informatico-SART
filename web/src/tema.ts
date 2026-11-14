import { createTheme } from '@mui/material/styles'

// Tema de MUI con los valores de DESIGN.md (los mismos tokens que App.scss). Si cambias un color aquí,
// cámbialo también en App.scss y en DESIGN.md.
export const tema = createTheme({
  palette: {
    primary: { main: '#417f88', dark: '#336a72', light: '#8fc6cd', contrastText: '#ffffff' },
    secondary: { main: '#1b3352', light: '#2a4566', contrastText: '#ffffff' },
    error: { main: '#a3261d' },
    warning: { main: '#ad430c' },
    success: { main: '#1d6b45' },
    text: { primary: '#283746', secondary: '#556677' },
    background: { default: '#edf2f2', paper: '#ffffff' },
    divider: '#d9e1e3',
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: '"Noto Sans", "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    h1: { fontFamily: '"Figtree", "Noto Sans", sans-serif', fontWeight: 700 },
    h2: { fontFamily: '"Figtree", "Noto Sans", sans-serif', fontWeight: 700 },
    h3: { fontFamily: '"Figtree", "Noto Sans", sans-serif', fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiButton: { styleOverrides: { root: { borderRadius: 999 } } },
  },
})
