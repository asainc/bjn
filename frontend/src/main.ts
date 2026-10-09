/** Inicialização zoneless nativa e configuração carregada via HttpClient. */
import { inject, provideAppInitializer, provideZonelessChangeDetection } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { AppComponent } from './app/app.component';
import { ApiConfiguration } from './app/core/config';
import { routes } from './app/app.routes';

bootstrapApplication(AppComponent, {providers:[provideZonelessChangeDetection(),provideHttpClient(withFetch()),provideRouter(routes),provideAppInitializer(() => inject(ApiConfiguration).load())]}).catch(() => {
  const notice = document.createElement('p');
  notice.textContent = 'Não foi possível iniciar a aplicação. Verifique a configuração de conexão e recarregue a página.';
  notice.setAttribute('role','alert');
  document.body.appendChild(notice);
});
