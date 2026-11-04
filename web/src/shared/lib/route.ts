import { useEffect, useState } from 'react';

export const ROUTES = ['home', 'data', 'params', 'train', 'results', 'check'] as const;
export type Route = (typeof ROUTES)[number];

const read = (): Route => {
  const h = location.hash.slice(1);
  return (ROUTES as readonly string[]).includes(h) ? (h as Route) : 'home';
};

export function go(route: Route): void {
  if (location.hash !== '#' + route) location.hash = route;
  window.scrollTo(0, 0);
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}
