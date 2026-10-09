/** API BJN: o backend é a única fonte do questionário. */
import {HttpClient} from '@angular/common/http';
import {inject, Injectable} from '@angular/core';
import {ApiConfiguration} from './config';
import {ChatResponse} from './contracts';
export type ScriptQuestion = {id:string; label:string; type:'choice'|'multi'|'text'|'number'|'boolean'; source_page:number; options?:{value:string;label:string}[]; when?:Record<string,string>};
export type ScriptWorkflow = {source:string; source_pages:number;version:string;questions:ScriptQuestion[];human_channel:string};
export type Assessment = {status:string;human_review_required:boolean;reasons:string[];suggested_clause_topics:string[];source_status:string};
@Injectable({providedIn:'root'})
export class BjnApiService {
 private readonly http=inject(HttpClient);private readonly config=inject(ApiConfiguration);
 bookPreview(answers:Record<string,string|string[]|number>){return this.http.post<{clauses:{clause_id:string;title:string;status:string;sections:{heading:string;text:string}[];source_page:number;remaining_pages:number}[];note:string}>(`${this.config.baseUrl}/bjn/previa-clausulas`,{answers});}
 bookImageUrl(path:string){return `${this.config.baseUrl}${path}`;}
 questionnaire(){return this.http.get<ScriptWorkflow>(`${this.config.baseUrl}/bjn/questionario`);}
 evaluate(answers:Record<string,string|string[]|number>){return this.http.post<Assessment>(`${this.config.baseUrl}/bjn/avaliar`,{answers});}
 chat(pergunta:string){return this.http.post<ChatResponse>(`${this.config.baseUrl}/bjn/chat`,{pergunta});}
}
