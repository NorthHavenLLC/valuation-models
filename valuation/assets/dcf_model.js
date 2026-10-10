/* Exact forecast DCF arithmetic shared by the UI and the Node regression tests. */
(function(root) {
  'use strict';
  const finite = Number.isFinite;
  function evaluate(model, method, rate, terminal) {
    if (!['gordon', 'exit'].includes(method) || !finite(rate) || rate <= -1 || !finite(terminal) ||
        !finite(model.shares) || model.shares <= 0 || !model.flows.length ||
        !model.flows.every(finite) || (method === 'gordon' && rate <= terminal)) return null;
    const offset = model.midYear ? 0.5 : 0;
    const explicit = model.flows.reduce((sum, flow, i) => sum + flow / (1 + rate) ** (i + 1 - offset), 0);
    const factor = (1 + rate) ** -(model.flows.length - offset);
    const tv = method === 'gordon' ? model.flows.at(-1) * (1 + terminal) / (rate - terminal) : model.finalEbitda * terminal;
    const terminalPV = tv * factor;
    const enterprise = explicit + terminalPV;
    const price = (enterprise - model.netDebt) / model.shares;
    if (![explicit, terminalPV, enterprise, price].every(finite)) return null;
    return {price, explicit, terminalPV, enterprise, equity: enterprise - model.netDebt,
      explicitPerShare: explicit/model.shares, terminalPerShare: terminalPV/model.shares,
      debtPerShare: model.netDebt/model.shares,
      terminalShare: enterprise > 0 ? terminalPV/enterprise : null};
  }
  function linspace(low, high, count=51, include=null) {
    const values = Array.from({length: count}, (_, i) => low + (high-low)*i/(count-1));
    if (finite(include) && include >= low && include <= high) {
      const nearest = values.reduce((best, v, i) => Math.abs(v-include) < Math.abs(values[best]-include) ? i : best, 0);
      values[nearest] = include;
      values.sort((a,b) => a-b);
    }
    return values;
  }
  function roots(fn, target, bounds, count=160) {
    if (!finite(target)) return [];
    const xs = linspace(bounds[0], bounds[1], count+1), found = [];
    const tolerance = 1e-7 * Math.max(1, Math.abs(target));
    const value = x => { const v=fn(x); return finite(v) ? v-target : null; };
    const add = x => { if (!found.some(v => Math.abs(v-x) < 1e-7)) found.push(x); };
    for (let i=0; i<xs.length; i++) {
      let lo=xs[i], a=value(lo);
      if (a === null) continue;
      if (Math.abs(a) < tolerance) add(lo);
      if (i === xs.length-1) break;
      let hi=xs[i+1], b=value(hi);
      if (b === null || a*b >= 0) continue;
      let mid, residual;
      for (let j=0; j<70; j++) {
        mid=(lo+hi)/2; residual=value(mid);
        if (residual === null) break;
        if (Math.abs(residual) < tolerance) break;
        if (a*residual <= 0) hi=mid;
        else { lo=mid; a=residual; }
      }
      // Reject sign changes across singularities rather than reporting a false root.
      if (residual !== null && Math.abs(residual) < tolerance) add(mid);
    }
    return found;
  }
  function targetTerminal(model, method, rate, target) {
    if (!finite(target) || rate <= -1) return null;
    const probe=evaluate(model, 'exit', rate, 0);
    if (!probe) return null;
    const factor=(1+rate) ** -(model.flows.length-(model.midYear ? 0.5 : 0));
    const requiredTV=(target*model.shares+model.netDebt-probe.explicit)/factor;
    let terminal;
    if (method === 'exit') terminal=model.finalEbitda !== 0 ? requiredTV/model.finalEbitda : null;
    else {
      const flow=model.flows.at(-1), divisor=requiredTV+flow;
      terminal=divisor !== 0 ? (requiredTV*rate-flow)/divisor : null;
    }
    if (!finite(terminal)) return null;
    const check=evaluate(model, method, rate, terminal);
    return check && Math.abs(check.price-target) < 1e-7*Math.max(1,Math.abs(target)) ? terminal : null;
  }
  function scenario(model, method, rate, terminal, target) {
    const result=evaluate(model,method,rate,terminal);
    return {method, rate, terminal, target, result};
  }
  function csv(rows) {
    const quote=v => '"'+String(v ?? '').replaceAll('"','""')+'"';
    const headers=['Scenario','Method','WACC','Terminal input','Price per share','Target','Difference to target','Explicit PV per share','Terminal PV per share','Terminal share of EV'];
    const values=rows.map((r,i)=>[r.name || `Scenario ${i+1}`,r.method,r.rate,r.terminal,r.result?.price,r.target,
      r.result ? r.result.price-r.target : null,r.result?.explicitPerShare,r.result?.terminalPerShare,r.result?.terminalShare]);
    return [headers,...values].map(row=>row.map(quote).join(',')).join('\r\n');
  }
  const api={evaluate, linspace, roots, targetTerminal, scenario, csv};
  if (typeof module !== 'undefined' && module.exports) module.exports=api;
  root.ValuationModel=api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
