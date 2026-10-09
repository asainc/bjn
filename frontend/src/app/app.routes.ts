/** Rotas atuais da plataforma jurídica. */
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'ai-ready',
    loadComponent: () => import('./ai-ready/ai-ready-page.component').then(module => module.AiReadyPageComponent),
  },
  {
    path: 'bjn',
    loadComponent: () => import('./bjn/bjn-page.component').then(module => module.BjnPageComponent),
  },
  {path: '', pathMatch: 'full', redirectTo: 'ai-ready'},
  {path: '**', redirectTo: 'ai-ready'},
];
