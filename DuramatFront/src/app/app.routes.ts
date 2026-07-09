import { Routes } from '@angular/router';
import { Home } from './components/home/home';
import { Result } from './components/result/result';

export const routes: Routes = [
    { path: '', component: Home },
    { path: 'result', component: Result },
    { path: '**', redirectTo: '' }
];
