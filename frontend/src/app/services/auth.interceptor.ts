import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

const publicAuthPaths = ['/auth/login', '/auth/forgot-password', '/auth/reset-password'];

function isPublicAuthRequest(url: string) {
  return publicAuthPaths.some(path => url.includes(path));
}

function notifySessionExpired() {
  localStorage.removeItem('pyflow_token');
  localStorage.removeItem('pyflow_user');
  window.dispatchEvent(new CustomEvent('pyflow:session-expired'));
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = localStorage.getItem('pyflow_token');
  const authReq = !token || req.headers.has('Authorization')
    ? req
    : req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });

  return next(authReq).pipe(
    catchError(error => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        !isPublicAuthRequest(req.url)
      ) {
        notifySessionExpired();
      }
      return throwError(() => error);
    })
  );
};
