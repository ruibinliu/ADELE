import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class FileUploadService {

  private backendUri = environment.serverUri;
  

  constructor(private http: HttpClient) { }

  uploadFile(file: File, projectId: string): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);

    return this.http.post(`${this.backendUri}/si/upload/file/${file.name}`, formData, {
      withCredentials: true
    });
  }
}