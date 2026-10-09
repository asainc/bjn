/** Página neutra preservada para evolução futura do projeto BJN. */
import { Component, computed, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-template-page',
  standalone: true,
  imports: [RouterLink],
  template: `
    <main class="template-page">
      <header class="template-heading">
        <div>
          <span class="eyebrow">Aplicação</span>
          <h1>{{ title() }}</h1>
          <p>{{ description() }}</p>
        </div>
        <a class="button" routerLink="/ai-ready">Abrir AI Ready</a>
      </header>
      <section class="surface template-hero">
        <div class="template-hero-badge">{{ initials() }}</div>
        <div>
          <h2>{{ stage() }}</h2>
          <p>Estrutura visual preservada para receber uma jornada própria quando o escopo do projeto for definido.</p>
        </div>
      </section>
    </main>
  `,
})
export class ApplicationTemplatePageComponent {
  private readonly route = inject(ActivatedRoute);
  readonly title = computed(() => String(this.route.snapshot.data['title'] ?? 'Aplicação'));
  readonly description = computed(() => String(this.route.snapshot.data['description'] ?? 'Projeto em preparação.'));
  readonly initials = computed(() => String(this.route.snapshot.data['initials'] ?? 'AP'));
  readonly stage = computed(() => String(this.route.snapshot.data['stage'] ?? 'Em preparação'));
}
