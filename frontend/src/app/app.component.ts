/** Shell principal preservando a identidade visual do projeto original. */
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { NotificationsComponent } from './shared/notifications.component';

type ApplicationKey = 'bjn' | 'ai-ready';

type ApplicationDescriptor = {
  key: ApplicationKey;
  label: string;
  subtitle: string;
  route: string;
  badge: string;
};

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet, NotificationsComponent],
  template: `
    <div class="application-shell" [class.nav-collapsed]="navigationCollapsed()">
      <aside class="platform-sidebar" [class.collapsed]="navigationCollapsed()" aria-label="Aplicações do sistema">
        <div class="platform-sidebar-header">
          <button
            type="button"
            class="sidebar-toggle global-toggle"
            (click)="toggleNavigation()"
            [attr.aria-expanded]="!navigationCollapsed()"
            aria-controls="platform-nav"
            aria-label="Expandir ou retrair aplicações"
          >☰</button>
          @if (!navigationCollapsed()) {
            <div class="platform-branding">
              <span class="brand-mark" aria-hidden="true"></span>
              <div>
                <strong>Plataforma jurídica</strong>
                <small>Aplicações inteligentes</small>
              </div>
            </div>
          }
        </div>

        <nav id="platform-nav" class="platform-nav">
          @for (application of applications; track application.key) {
            <a
              [routerLink]="application.route"
              routerLinkActive="active"
              [routerLinkActiveOptions]="{ exact: false }"
              class="platform-link"
              [attr.title]="application.label"
            >
              <span class="platform-link-badge" aria-hidden="true">{{ application.badge }}</span>
              @if (!navigationCollapsed()) {
                <span class="platform-link-copy">
                  <strong>{{ application.label }}</strong>
                  <small>{{ application.subtitle }}</small>
                </span>
              }
            </a>
          }
        </nav>
      </aside>

      <div class="application-content-shell">
        <header class="application-bar">
          <div class="application-bar-main">
            <a class="brand brand--app" [routerLink]="activeApplication().route">
              <span class="brand-mark" aria-hidden="true"></span>
              <span class="brand-copy">
                <small>Aplicação</small>
                <strong>{{ activeApplication().label }}</strong>
              </span>
            </a>

            @if (activeApplication().key === 'bjn') {
              <nav aria-label="Navegação BJN" class="top-level-nav top-level-nav--bjn">
                <a routerLink="/bjn" routerLinkActive="context-active" [routerLinkActiveOptions]="{exact:true}">Minutas</a>
                <a routerLink="/bjn/demandas" routerLinkActive="context-active" [routerLinkActiveOptions]="{exact:false}">Demandas</a>
                <a routerLink="/bjn/demandas/nova" class="top-new-demand">+ Nova demanda</a>
              </nav>
            }
            @if (activeApplication().key === 'ai-ready') {
              <nav aria-label="Contexto da aplicação" class="top-level-nav top-level-nav--context">
                <span>Visão do processo</span>
                <span>Linha do tempo</span>
                <span>Assistente IA</span>
              </nav>
            }
          </div>

          <span class="product-context">{{ headerContext() }}</span>
        </header>

        <app-notifications />
        <div class="route-content"><router-outlet /></div>
      </div>
    </div>
  `,
})
export class AppComponent {
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly navigationCollapsed = signal(false);
  readonly currentUrl = signal(this.router.url);
  readonly applications: ApplicationDescriptor[] = [
    {key: 'ai-ready', label: 'AI Ready', subtitle: 'Inteligência processual', route: '/ai-ready', badge: 'AI'},
    {key: 'bjn', label: 'BJN', subtitle: 'Minutas e demandas', route: '/bjn', badge: 'BJ'},
  ];

  readonly activeApplication = computed(() => this.currentUrl().startsWith('/bjn') ? this.applications[1] : this.applications[0]);
  readonly headerContext = computed(() => this.activeApplication().key === 'ai-ready' ? 'Processos cíveis' : 'Minutas e demandas');

  constructor() {
    this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd), takeUntilDestroyed(this.destroyRef))
      .subscribe(event => this.currentUrl.set(event.urlAfterRedirects));
  }

  toggleNavigation(): void {
    this.navigationCollapsed.set(!this.navigationCollapsed());
  }
}
