// Cross-domain entity links — the graph moat made navigable. Given an entity on
// one surface, resolve the routes that view the SAME entity on other surfaces, so
// a user can trace an instrument → its supply chain → its digital twin → the
// knowledge graph → the economy board → the news, without dead-ends.
import { nodesForMarketSymbol } from '../../data/supplyChainFixture';
import { twins } from '../../data/twinFixture';

export interface CrossLink {
  label: string;
  surface: string;
  icon: string;
  to: { path: string; query?: Record<string, string> };
}

// Instrument (Markets) → the other surfaces that hold the same real-world entity.
export function crossLinksForInstrument(symbol: string): CrossLink[] {
  const links: CrossLink[] = [];
  const nodes = nodesForMarketSymbol(symbol);
  if (nodes[0]) {
    links.push({ label: 'Supply chain', surface: 'Supply Chain', icon: '⛓', to: { path: '/analytics/supply-chain', query: { node: nodes[0].id } } });
    links.push({ label: 'Knowledge graph', surface: 'Knowledge Graph', icon: '◈', to: { path: '/knowledge/graph' } });
  }
  const twin = twins.find((t) => t.headlineSymbol === symbol);
  if (twin) links.push({ label: 'Digital twin', surface: 'Digital Twin', icon: '◉', to: { path: '/analytics/digital-twin', query: { twin: twin.id } } });
  links.push({ label: 'Sector board', surface: 'Economy', icon: '▤', to: { path: '/capability/economic-prophet' } });
  links.push({ label: 'In the news', surface: 'News', icon: '❑', to: { path: '/news' } });
  return links;
}

// Law docket → the entities it affects (Markets instruments, Economy sectors, News).
export function crossLinksForDocket(affects: { sectors?: string[]; symbols?: string[]; topics?: string[] }): CrossLink[] {
  const links: CrossLink[] = [];
  const sym = affects.symbols?.[0];
  if (sym) links.push({ label: `Affected: ${sym}`, surface: 'Markets', icon: '▲', to: { path: '/markets/equities-preferreds', query: { sym } } });
  if (affects.sectors && affects.sectors.length) links.push({ label: 'Sector impact', surface: 'Economy', icon: '▤', to: { path: '/capability/economic-prophet' } });
  links.push({ label: 'Related coverage', surface: 'News', icon: '❑', to: { path: '/news' } });
  return links;
}

// Supply-chain commodity → Markets + Digital Twin (the reciprocal direction).
export function crossLinksForChain(marketSymbol: string | undefined, twinId?: string): CrossLink[] {
  const links: CrossLink[] = [];
  if (marketSymbol) links.push({ label: 'Market', surface: 'Markets', icon: '▲', to: { path: '/markets/real-assets', query: { sym: marketSymbol } } });
  if (twinId) links.push({ label: 'Digital twin', surface: 'Digital Twin', icon: '◉', to: { path: '/analytics/digital-twin', query: { twin: twinId } } });
  links.push({ label: 'Knowledge graph', surface: 'Knowledge Graph', icon: '◈', to: { path: '/knowledge/graph' } });
  return links;
}
