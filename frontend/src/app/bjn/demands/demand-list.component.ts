/** Lista de demandas com busca e filtros, sem resultados fictícios. */
import {CommonModule} from '@angular/common';
import {Component,inject,OnInit,signal} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {RouterLink} from '@angular/router';
import {firstValueFrom} from 'rxjs';
import {BjnDemandApiService,DemandStatus,DemandSummary} from '../../core/bjn-demand-api.service';
import {demandStatusLabels,friendlyApiError,readableDate,selectableStatuses} from './demand-ui';

@Component({selector:'app-bjn-demand-list',standalone:true,imports:[CommonModule,FormsModule,RouterLink],styleUrl:'./demands.scss',template:`
<main class="demand-shell">
  <nav class="demand-crumb" aria-label="Navegação"><a routerLink="/bjn">BJN</a><span>/</span><strong>Demandas</strong></nav>
  <header class="demand-heading"><div><span class="eyebrow">BJN · ATENDIMENTO JURÍDICO</span><h1>Minhas demandas</h1><p>Acompanhe solicitações, documentos enviados, responsáveis e mudanças de status.</p></div>
  <a routerLink="/bjn/demandas/nova" class="primary demand-new-action">+ Nova demanda</a></header>
  <section class="surface demand-list-card" aria-labelledby="demand-list-title">
    <div class="demand-list-toolbar"><div><h2 id="demand-list-title">Solicitações</h2><small>{{items().length}} demanda(s) encontrada(s)</small></div>
      <div class="demand-filters"><label class="sr-only" for="search-demands">Buscar demandas</label>
        <input id="search-demands" placeholder="Buscar por número, título ou área" [(ngModel)]="search" (keyup.enter)="load()" />
        <label class="sr-only" for="filter-status">Status</label>
        <select id="filter-status" [(ngModel)]="status" (change)="load()"><option value="">Todos os status</option>
          @for(value of statuses;track value){<option [value]="value">{{labels[value]}}</option>}
        </select><button type="button" (click)="load()" [disabled]="busy()">Buscar</button></div>
    </div>
    <div class="bjn-search-extra" aria-label="Filtros complementares">
      <label>Data de cadastro <input type="date" [(ngModel)]="fromDate" /></label>
      <label>Agência <input maxlength="40" [(ngModel)]="branch" placeholder="Agência" /></label>
      <label>Nome ou e-mail <input maxlength="120" [(ngModel)]="registeredEmail" placeholder="E-mail de quem cadastrou" /></label>
      <label>CPF do cliente <input maxlength="14" inputmode="numeric" [(ngModel)]="clientCPF" placeholder="Busca protegida" /></label>
      <button type="button" class="demand-outlined" (click)="load()" [disabled]="busy()">Aplicar filtros</button>
    </div>
    @if(error()){<p class="demand-error" role="alert">{{error()}} <button type="button" (click)="load()">Tentar novamente</button></p>}
    @if(busy()){<p class="demand-loading">Carregando demandas...</p>}
    @else if(!items().length){<div class="demand-empty"><span aria-hidden="true" class="demand-empty-icon">▤</span><h3>Nenhuma demanda encontrada</h3>
      <p>@if(search||status){Ajuste os filtros para consultar outras solicitações.}@else{Cadastre sua primeira demanda para acompanhar o atendimento jurídico em um só lugar.}</p>
      <a routerLink="/bjn/demandas/nova" class="demand-outlined">Cadastrar demanda</a></div>}
    @else {<div class="demand-table-scroll"><table class="demand-table"><thead><tr><th>Demanda</th><th>Área de consulta</th><th>Status</th><th>Advogado responsável</th><th>Atualização</th><th><span class="sr-only">Ação</span></th></tr></thead>
      <tbody>@for(item of items();track item.id){<tr><td><a class="demand-strong-link" [routerLink]="['/bjn/demandas',item.id]">{{item.title}}</a><small>{{item.id}}</small></td>
        <td>{{item.consult_area}}</td><td><span class="demand-pill" [attr.data-status]="item.status">{{labels[item.status]}}</span></td>
        <td>{{item.lawyer_email || 'Aguardando distribuição'}}</td><td>{{date(item.updated_at)}}</td>
        <td><a class="demand-table-link" [routerLink]="['/bjn/demandas',item.id]" [attr.aria-label]="'Acompanhar '+item.id">Acompanhar →</a></td></tr>}
      </tbody></table></div>}
  </section>
</main>`})
export class BjnDemandListComponent implements OnInit {
  private readonly api=inject(BjnDemandApiService);
  readonly items=signal<DemandSummary[]>([]);
  readonly busy=signal(false);
  readonly error=signal('');
  readonly statuses=selectableStatuses;
  readonly labels=demandStatusLabels;
  readonly date=readableDate;
  search='';status='';fromDate='';branch='';registeredEmail='';clientCPF='';
  ngOnInit():void{void this.load();}
  async load():Promise<void>{this.busy.set(true);this.error.set('');try{const result=await firstValueFrom(this.api.list(this.search,this.status,{from_date:this.fromDate,branch:this.branch,registered_email:this.registeredEmail,client_cpf:this.clientCPF}));this.items.set(result.items);}catch(error){this.error.set(friendlyApiError(error));}finally{this.busy.set(false);}}
}
