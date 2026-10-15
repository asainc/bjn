/** Rotas atuais da plataforma jurídica. */
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'ai-ready',
    loadComponent: () => import('./ai-ready/ai-ready-page.component').then(module => module.AiReadyPageComponent),
  },
  {
    path: 'bjn/demandas/nova',
    loadComponent: () => import('./bjn/demands/demand-new.component').then(module => module.BjnDemandNewComponent),
  },
  {
    path: 'bjn/demandas/:id',
    loadComponent: () => import('./bjn/demands/demand-detail.component').then(module => module.BjnDemandDetailComponent),
  },
  {
    path: 'bjn/demandas',
    loadComponent: () => import('./bjn/demands/demand-list.component').then(module => module.BjnDemandListComponent),
  },
  {
    path: 'bjn',
    loadComponent: () => import('./bjn/bjn-page.component').then(module => module.BjnPageComponent),
  },
  {path: '', pathMatch: 'full', redirectTo: 'ai-ready'},
  {path: '**', redirectTo: 'ai-ready'},
];
