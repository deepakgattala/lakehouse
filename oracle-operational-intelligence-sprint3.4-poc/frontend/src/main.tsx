import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material';
import App from './App';
const theme=createTheme({palette:{mode:'light',primary:{main:'#2563eb'},background:{default:'#f4f6f8'}},shape:{borderRadius:8},typography:{fontFamily:'Inter, system-ui, sans-serif'}});
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={new QueryClient()}><ThemeProvider theme={theme}><CssBaseline/><App/></ThemeProvider></QueryClientProvider></React.StrictMode>);
