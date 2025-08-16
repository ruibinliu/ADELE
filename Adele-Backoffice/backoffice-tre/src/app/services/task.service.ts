import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class TaskService {

  backendUri = environment.backendUrl + '/api';

  constructor(private http: HttpClient) { }

  getTasks() {
    return this.http.get(`${this.backendUri}/tasks`);
  }

  /** List all files in tes/{user}/ folders for validation */
  getOutputList() {
    return this.http.get<{ files: string[] }>(`${this.backendUri}/si/get/output/list`);
  }

  /** Stream a file from tes/{user}/{filename} */
  viewUserFile(user: string, filename: string) {
    return this.http.get(`${this.backendUri}/si/view/${user}/${filename}`);
  }

  /** Approve a file by moving it to results/{user}/{filename} */
  approveFile(user: string, filename: string) {
    return this.http.post(`${this.backendUri}/si/approve/${user}/${filename}`, {});
  }

  /** Reject a file by deleting it from tes/{user}/{filename} */
  rejectFile(user: string, filename: string) {
    return this.http.post(`${this.backendUri}/si/reject/${user}/${filename}`, {});
  }

}
