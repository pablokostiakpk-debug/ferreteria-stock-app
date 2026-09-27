const state = {
  token: localStorage.getItem('ferreteria_token'),
  user: JSON.parse(localStorage.getItem('ferreteria_user') || 'null'),
  page: 'dashboard',
  movementType: 'RETIRO',
  batchMode: false,
  scannedProduct: null,
  batchCart: [],
  lastSearch: '',
};

const $ = (sel, root=document) => root.querySelector(sel);
const $$ = (sel, root=document) => [...root.querySelectorAll(sel)];
const main = $('#mainContent');

function money(v){
  if(v === null || v === undefined || v === '') return '-';
  return new Intl.NumberFormat('es-AR',{style:'currency',currency:'ARS',maximumFractionDigits:2}).format(Number(v));
}
function qty(v){
  const n = Number(v || 0);
  return Number.isInteger(n) ? String(n) : n.toLocaleString('es-AR',{maximumFractionDigits:3});
}
function esc(s=''){
  return String(s ?? '').replace(/[&<>'"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function fmtDate(v){
  if(!v) return '-';
  return new Date(v).toLocaleString('es-AR',{dateStyle:'short',timeStyle:'short'});
}
function statusBadge(p){
  const current=Number(p.stock_current), min=Number(p.stock_min);
  if(current<=0) return '<span class="badge danger">🔴 Sin stock</span>';
  if(current<=min) return '<span class="badge warn">🟡 Stock bajo</span>';
  return '<span class="badge ok">🟢 Stock normal</span>';
}
function toast(message, type='ok'){
  const el=$('#toast'); el.textContent=message; el.className=`toast ${type}`;
  clearTimeout(window.__toastTimer); window.__toastTimer=setTimeout(()=>el.classList.add('hidden'),3500);
}
function openModal(html){ $('#modalBody').innerHTML=html; $('#modal').classList.remove('hidden'); }
function closeModal(){ $('#modal').classList.add('hidden'); $('#modalBody').innerHTML=''; }
$('#modalClose').onclick=closeModal;
$('#modal').addEventListener('click',e=>{ if(e.target.id==='modal') closeModal(); });

async function api(path, options={}){
  const headers={...(options.headers||{})};
  if(state.token) headers.Authorization=`Bearer ${state.token}`;
  if(options.body && !(options.body instanceof FormData) && typeof options.body !== 'string'){
    headers['Content-Type']='application/json'; options.body=JSON.stringify(options.body);
  }
  const res=await fetch(path,{...options,headers});
  if(res.status===401){ logout(); throw new Error('Sesión vencida'); }
  if(!res.ok){
    let msg='Ocurrió un error';
    try{ const data=await res.json(); msg=data.detail || msg; }catch{}
    throw new Error(typeof msg==='string'?msg:JSON.stringify(msg));
  }
  const ct=res.headers.get('content-type')||'';
  return ct.includes('application/json')?res.json():res;
}

function isAdmin(){ return state.user?.role==='ADMINISTRADOR'; }
function showApp(){
  $('#loginView').classList.add('hidden'); $('#appView').classList.remove('hidden');
  $('#userName').textContent=`${state.user?.full_name || state.user?.username} · ${state.user?.role}`;
  navigate(state.page || 'dashboard');
}
function showLogin(){ $('#appView').classList.add('hidden'); $('#loginView').classList.remove('hidden'); }
function logout(){
  localStorage.removeItem('ferreteria_token'); localStorage.removeItem('ferreteria_user');
  state.token=null; state.user=null; showLogin();
}
$('#logoutBtn').onclick=logout;
$('#loginForm').addEventListener('submit',async e=>{
  e.preventDefault();
  try{
    const data=await api('/api/auth/token',{method:'POST',body:{username:$('#loginUser').value.trim(),password:$('#loginPassword').value}});
    state.token=data.access_token; state.user=data.user;
    localStorage.setItem('ferreteria_token',state.token); localStorage.setItem('ferreteria_user',JSON.stringify(state.user));
    showApp();
  }catch(err){ toast(err.message,'error'); }
});

$('#menuBtn').onclick=()=>$('#sidebar').classList.toggle('open');
$$('.nav-btn').forEach(b=>b.onclick=()=>navigate(b.dataset.page));
$('#globalSearch').addEventListener('keydown',e=>{
  if(e.key==='Enter'){
    state.lastSearch=e.target.value.trim();
    navigate('products');
  }
});

function navigate(page){
  state.page=page;
  $$('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
  $('#sidebar').classList.remove('open');
  const fn={dashboard:renderDashboard,movement:renderMovement,products:renderProducts,replenishment:renderReplenishment,history:renderHistory,suppliers:renderSuppliers}[page]||renderDashboard;
  fn();
}

async function renderDashboard(){
  main.innerHTML='<div class="card">Cargando panel...</div>';
  try{
    const d=await api('/api/dashboard');
    main.innerHTML=`
      <div class="page-head"><div><h1>Panel principal</h1><p>Resumen rápido del inventario.</p></div></div>
      <section class="grid-kpi">
        <div class="kpi"><div class="label">Total de productos</div><div class="value">${d.total_products}</div></div>
        <div class="kpi warn"><div class="label">Stock bajo</div><div class="value">${d.low_stock}</div></div>
        <div class="kpi danger"><div class="label">Sin stock</div><div class="value">${d.out_of_stock}</div></div>
        <div class="kpi"><div class="label">Movimientos hoy</div><div class="value">${d.movements_today}</div></div>
      </section>
      <section class="quick-actions">
        <button class="btn scan-big" data-go="movement">▦ ESCANEAR PRODUCTO</button>
        <button class="btn btn-light" data-go="products">PRODUCTOS</button>
        <button class="btn btn-light" data-go="replenishment">REPOSICIÓN</button>
        <button class="btn btn-light" data-go="history">HISTORIAL</button>
        <button class="btn btn-light" data-go="suppliers">PROVEEDORES</button>
      </section>
      <div class="card"><h2>Últimos movimientos</h2>${movementTable(d.recent_movements)}</div>`;
    $$('[data-go]').forEach(b=>b.onclick=()=>navigate(b.dataset.go));
  }catch(err){ main.innerHTML=`<div class="alert-box danger">${esc(err.message)}</div>`; }
}

function movementTable(items){
  if(!items?.length) return '<div class="empty">Todavía no hay movimientos.</div>';
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Fecha</th><th>Producto</th><th>Tipo</th><th>Cantidad</th><th>Antes</th><th>Después</th></tr></thead><tbody>
    ${items.map(m=>`<tr><td>${fmtDate(m.created_at)}</td><td>${esc(m.product_name_snapshot)}<br><small class="muted">${esc(m.barcode_snapshot)}</small></td><td>${esc(m.movement_type)}</td><td>${qty(m.quantity)}</td><td>${qty(m.stock_before)}</td><td>${qty(m.stock_after)}</td></tr>`).join('')}
  </tbody></table></div>`;
}

function renderMovement(){
  state.scannedProduct=null;
  main.innerHTML=`
    <div class="page-head"><div><h1>Movimiento de Stock</h1><p>Escaneá con lector USB o usá la cámara del celular.</p></div>
      <div class="actions"><button id="cameraBtn" class="btn btn-blue">📷 Usar cámara</button></div></div>
    <div class="scanner-shell">
      <div>
        <div class="card">
          <div class="operation-toggle">
            <button id="withdrawBtn" class="btn btn-light ${state.movementType==='RETIRO'?'active':''}">RETIRO</button>
            <button id="incomeBtn" class="btn btn-light ${state.movementType==='INGRESO'?'active':''}">INGRESO</button>
          </div>
          <div style="height:12px"></div>
          <input id="barcodeInput" class="scanner-input" autocomplete="off" inputmode="numeric" placeholder="Escanear código de barras" autofocus>
          <p class="scanner-help">El lector USB debe terminar el código con Enter. También podés escribirlo manualmente.</p>
        </div>
        <div id="scanResult" class="card"><div class="empty">Esperando un producto...</div></div>
      </div>
      <div>
        <div class="card">
          <label style="display:flex;align-items:center;gap:10px;font-weight:800"><input id="batchMode" type="checkbox" style="width:auto" ${state.batchMode?'checked':''}> Retiro/ingreso de varios productos</label>
          <p class="muted">En modo lista, cada escaneo agrega el artículo y al final confirmás todo junto.</p>
        </div>
        <div id="batchPanel" class="card">${renderBatchCart()}</div>
      </div>
    </div>`;
  $('#barcodeInput').focus();
  $('#barcodeInput').addEventListener('keydown',e=>{ if(e.key==='Enter'){ e.preventDefault(); scanBarcode(e.target.value); } });
  $('#withdrawBtn').onclick=()=>{state.movementType='RETIRO';renderMovement();};
  $('#incomeBtn').onclick=()=>{state.movementType='INGRESO';renderMovement();};
  $('#batchMode').onchange=e=>{state.batchMode=e.target.checked; renderMovement();};
  $('#cameraBtn').onclick=startCameraScanner;
  bindBatchActions();
  bindGlobalScanner();
}

function bindGlobalScanner(){
  let buffer='', last=0;
  window.onkeydown=(e)=>{
    if(state.page!=='movement') return;
    const tag=document.activeElement?.tagName;
    if(tag==='INPUT' || tag==='TEXTAREA' || tag==='SELECT') return;
    const now=Date.now(); if(now-last>120) buffer=''; last=now;
    if(e.key==='Enter'){
      if(buffer.length>=4){ scanBarcode(buffer); buffer=''; }
    } else if(e.key.length===1){ buffer+=e.key; }
  };
}

async function scanBarcode(raw){
  const code=String(raw||'').trim(); if(!code) return;
  const input=$('#barcodeInput'); if(input){input.value='';input.focus();}
  try{
    const p=await api(`/api/products/barcode/${encodeURIComponent(code)}`);
    if(state.batchMode){
      const existing=state.batchCart.find(x=>x.product.id===p.id);
      if(existing) existing.quantity=Number(existing.quantity)+1; else state.batchCart.push({product:p,quantity:1});
      $('#batchPanel').innerHTML=renderBatchCart(); bindBatchActions();
      toast(`${p.name} agregado a la lista`);
    }else{
      state.scannedProduct=p; renderScannedProduct(p);
    }
  }catch(err){
    if(err.message==='Producto no encontrado') renderNotFound(code); else toast(err.message,'error');
  }
}

function renderNotFound(code){
  const canAdd=isAdmin();
  $('#scanResult').innerHTML=`<div class="alert-box danger">Producto no encontrado<br><small>Código: ${esc(code)}</small></div>
    <div style="height:12px"></div>
    <button id="addUnknown" class="btn btn-primary btn-xl btn-block" ${canAdd?'':'disabled'}>AGREGAR PRODUCTO</button>
    ${canAdd?'':'<p class="muted">Tu usuario es VENDEDOR. Un administrador debe crear el producto.</p>'}`;
  if(canAdd) $('#addUnknown').onclick=()=>openProductForm(null,code);
}

function renderScannedProduct(p){
  const low=Number(p.stock_current)<=Number(p.stock_min);
  $('#scanResult').innerHTML=`
    <div class="product-focus">
      <div class="product-title"><div><div class="muted">PRODUCTO</div><h2>${esc(p.name)}</h2><div class="muted">Código: ${esc(p.barcode)}</div></div>${statusBadge(p)}</div>
      <div class="stock-number">${qty(p.stock_current)} <small style="font-size:18px">${esc(p.unit)}</small></div>
      <div class="stock-meta"><div><small>Stock actual</small><strong>${qty(p.stock_current)}</strong></div><div><small>Stock mínimo</small><strong>${qty(p.stock_min)}</strong></div><div><small>Stock objetivo</small><strong>${qty(p.stock_target)}</strong></div></div>
      ${low?'<div class="alert-box warn" style="margin-top:12px">⚠️ STOCK BAJO / REPOSICIÓN NECESARIA</div>':''}
      <div class="qty-control"><button id="qtyMinus">−</button><input id="moveQty" type="number" min="0.001" step="1" value="1"><button id="qtyPlus">+</button></div>
      <button id="confirmMove" class="btn btn-primary btn-xl btn-block">CONFIRMAR ${state.movementType}</button>
    </div>`;
  $('#qtyMinus').onclick=()=>{const i=$('#moveQty');i.value=Math.max(.001,Number(i.value||1)-1)};
  $('#qtyPlus').onclick=()=>{const i=$('#moveQty');i.value=Number(i.value||1)+1};
  $('#confirmMove').onclick=confirmSingleMovement;
}

async function confirmSingleMovement(){
  const p=state.scannedProduct; const amount=Number($('#moveQty').value);
  if(!p || !(amount>0)) return toast('Ingresá una cantidad válida','error');
  try{
    const m=await api('/api/stock/move',{method:'POST',body:{product_id:p.id,movement_type:state.movementType,quantity:amount}});
    const alert=Number(m.stock_after)<=Number(p.stock_min)?' · STOCK BAJO':'';
    toast(`Stock anterior ${qty(m.stock_before)} → nuevo ${qty(m.stock_after)}${alert}`);
    const fresh=await api(`/api/products/${p.id}`); state.scannedProduct=fresh; renderScannedProduct(fresh); $('#barcodeInput')?.focus();
  }catch(err){ toast(err.message,'error'); }
}

function renderBatchCart(){
  if(!state.batchCart.length) return '<h3>Lista temporal</h3><div class="empty">Todavía no agregaste productos.</div>';
  return `<h3>Lista temporal</h3><div class="table-wrap"><table class="table" style="min-width:560px"><thead><tr><th>Producto</th><th>Cantidad</th><th>Stock resultante</th><th></th></tr></thead><tbody>
    ${state.batchCart.map((x,i)=>{const s=Number(x.product.stock_current)+(state.movementType==='RETIRO'?-Number(x.quantity):Number(x.quantity));return `<tr><td>${esc(x.product.name)}</td><td><input class="cart-qty" data-i="${i}" type="number" min="0.001" step="1" value="${x.quantity}" style="width:100px"></td><td class="${s<0?'badge danger':''}">${qty(s)}</td><td><button class="btn btn-danger cart-remove" data-i="${i}">Quitar</button></td></tr>`}).join('')}
  </tbody></table></div><div style="height:12px"></div><button id="confirmBatch" class="btn btn-primary btn-xl btn-block">CONFIRMAR TODOS LOS ${state.movementType==='RETIRO'?'RETIROS':'INGRESOS'}</button>`;
}
function bindBatchActions(){
  $$('.cart-qty').forEach(i=>i.onchange=()=>{state.batchCart[Number(i.dataset.i)].quantity=Number(i.value);$('#batchPanel').innerHTML=renderBatchCart();bindBatchActions();});
  $$('.cart-remove').forEach(b=>b.onclick=()=>{state.batchCart.splice(Number(b.dataset.i),1);$('#batchPanel').innerHTML=renderBatchCart();bindBatchActions();});
  if($('#confirmBatch')) $('#confirmBatch').onclick=confirmBatch;
}
async function confirmBatch(){
  if(!state.batchCart.length) return;
  const invalid=state.batchCart.find(x=>!(Number(x.quantity)>0)); if(invalid) return toast('Revisá las cantidades','error');
  try{
    await api('/api/stock/batch',{method:'POST',body:{movement_type:state.movementType,items:state.batchCart.map(x=>({product_id:x.product.id,quantity:x.quantity}))}});
    toast('Todos los movimientos fueron registrados'); state.batchCart=[]; $('#batchPanel').innerHTML=renderBatchCart(); $('#scanResult').innerHTML='<div class="empty">Operación confirmada. Podés seguir escaneando.</div>';
  }catch(err){toast(err.message,'error');}
}

async function startCameraScanner(){
  if(!navigator.mediaDevices?.getUserMedia) return toast('Este navegador no permite usar la cámara','error');
  openModal(`<h2>Escanear con cámara</h2><p class="muted">Apuntá al código de barras. En producción la cámara necesita HTTPS.</p><div class="camera-box"><video id="cameraVideo" playsinline></video></div><p id="cameraStatus" class="muted">Iniciando cámara...</p>`);
  try{
    if(!window.ZXingBrowser) throw new Error('No se pudo cargar el lector de cámara. Revisá la conexión a internet.');
    const devices=await ZXingBrowser.BrowserCodeReader.listVideoInputDevices();
    const rear=devices.find(d=>/back|rear|environment|trasera/i.test(d.label)) || devices[devices.length-1];
    const reader=new ZXingBrowser.BrowserMultiFormatReader();
    const result=await reader.decodeOnceFromVideoDevice(rear?.deviceId, $('#cameraVideo'));
    const code=result.getText(); closeModal(); await scanBarcode(code);
  }catch(err){ const s=$('#cameraStatus'); if(s) s.textContent=err.message || 'No se pudo leer el código'; }
}

async function renderProducts(){
  main.innerHTML='<div class="card">Cargando productos...</div>';
  try{
    const q=state.lastSearch;
    const products=await api(`/api/products?limit=500${q?`&q=${encodeURIComponent(q)}`:''}`);
    main.innerHTML=`
      <div class="page-head"><div><h1>Productos</h1><p>${products.length} artículos encontrados.</p></div><div class="actions">
        ${isAdmin()?'<button id="newProduct" class="btn btn-primary">+ Agregar producto</button><label class="btn btn-light">Importar Excel/CSV<input id="importFile" type="file" accept=".csv,.xlsx,.xls" hidden></label>':''}
        <button id="exportExcel" class="btn btn-light">Exportar Excel</button><button id="exportCsv" class="btn btn-light">Exportar CSV</button>
      </div></div>
      <div class="filters"><input id="productSearch" class="wide" value="${esc(q)}" placeholder="Buscar nombre, código, marca, categoría o proveedor"><button id="doProductSearch" class="btn btn-dark">Buscar</button></div>
      <div class="table-wrap"><table class="table"><thead><tr><th>Producto</th><th>Código</th><th>Categoría</th><th>Stock</th><th>Mín.</th><th>Proveedor</th><th>Estado</th><th></th></tr></thead><tbody>
      ${products.map(p=>`<tr><td><strong>${esc(p.name)}</strong><br><small class="muted">${esc(p.brand||'')}</small></td><td>${esc(p.barcode)}</td><td>${esc(p.category?.name||'-')}</td><td>${qty(p.stock_current)} ${esc(p.unit)}</td><td>${qty(p.stock_min)}</td><td>${esc(p.supplier?.name||'-')}</td><td>${statusBadge(p)}</td><td>${isAdmin()?`<button class="btn btn-light edit-product" data-id="${p.id}">Editar</button>`:''}</td></tr>`).join('')}
      </tbody></table></div>`;
    state.lastSearch='';
    $('#doProductSearch').onclick=()=>{state.lastSearch=$('#productSearch').value.trim();renderProducts();};
    $('#productSearch').onkeydown=e=>{if(e.key==='Enter'){$('#doProductSearch').click();}};
    if(isAdmin()){
      $('#newProduct').onclick=()=>openProductForm();
      $('#importFile').onchange=e=>importProducts(e.target.files[0]);
      $$('.edit-product').forEach(b=>b.onclick=()=>openProductForm(products.find(p=>p.id===Number(b.dataset.id))));
    }
    $('#exportExcel').onclick=()=>downloadExport('/api/export/products.xlsx','stock_ferreteria.xlsx');
    $('#exportCsv').onclick=()=>downloadExport('/api/export/products.csv','stock_ferreteria.csv');
  }catch(err){ main.innerHTML=`<div class="alert-box danger">${esc(err.message)}</div>`; }
}

async function loadSuppliers(){ try{return await api('/api/suppliers');}catch{return [];} }
async function openProductForm(p=null,prefillBarcode=''){
  const suppliers=await loadSuppliers();
  const edit=!!p;
  openModal(`<h2>${edit?'Editar producto':'Agregar producto'}</h2>
    <form id="productForm"><div class="form-grid">
      <label>Código de barras<input id="pfBarcode" value="${esc(p?.barcode||prefillBarcode)}" required></label>
      <label>Nombre<input id="pfName" value="${esc(p?.name||'')}" required></label>
      <label class="full">Descripción<textarea id="pfDescription">${esc(p?.description||'')}</textarea></label>
      <label>Categoría<input id="pfCategory" value="${esc(p?.category?.name||'')}"></label>
      <label>Marca<input id="pfBrand" value="${esc(p?.brand||'')}"></label>
      <label>Unidad<select id="pfUnit">${['Unidad','Metro','Kilogramo','Litro','Caja','Bolsa','Otro'].map(u=>`<option ${u===(p?.unit||'Unidad')?'selected':''}>${u}</option>`).join('')}</select></label>
      ${edit?'':`<label>Stock inicial<input id="pfInitial" type="number" min="0" step="0.001" value="0"></label>`}
      <label>Stock mínimo<input id="pfMin" type="number" min="0" step="0.001" value="${p?.stock_min??0}"></label>
      <label>Stock objetivo<input id="pfTarget" type="number" min="0" step="0.001" value="${p?.stock_target??0}"></label>
      <label>Proveedor<select id="pfSupplier"><option value="">Sin proveedor</option>${suppliers.map(s=>`<option value="${s.id}" ${s.id===p?.supplier?.id?'selected':''}>${esc(s.name)}</option>`).join('')}</select></label>
      <label>Código proveedor<input id="pfSupplierCode" value="${esc(p?.supplier_code||'')}"></label>
      <label>Precio compra<input id="pfPurchase" type="number" min="0" step="0.01" value="${p?.purchase_price??''}"></label>
      <label>Precio venta<input id="pfSale" type="number" min="0" step="0.01" value="${p?.sale_price??''}"></label>
      <label>Ubicación<input id="pfLocation" value="${esc(p?.location||'')}"></label>
      <label class="full">Observaciones<textarea id="pfNotes">${esc(p?.notes||'')}</textarea></label>
    </div><div class="form-actions"><button type="button" class="btn btn-light" onclick="document.querySelector('#modalClose').click()">Cancelar</button><button class="btn btn-primary" type="submit">Guardar</button></div></form>`);
  $('#productForm').onsubmit=async e=>{
    e.preventDefault();
    const body={barcode:$('#pfBarcode').value.trim(),name:$('#pfName').value.trim(),description:$('#pfDescription').value||null,category:$('#pfCategory').value||null,brand:$('#pfBrand').value||null,unit:$('#pfUnit').value,stock_min:Number($('#pfMin').value||0),stock_target:Number($('#pfTarget').value||0),supplier_id:$('#pfSupplier').value?Number($('#pfSupplier').value):null,supplier_code:$('#pfSupplierCode').value||null,purchase_price:$('#pfPurchase').value?Number($('#pfPurchase').value):null,sale_price:$('#pfSale').value?Number($('#pfSale').value):null,location:$('#pfLocation').value||null,notes:$('#pfNotes').value||null};
    if(!edit) body.initial_stock=Number($('#pfInitial').value||0);
    try{ await api(edit?`/api/products/${p.id}`:'/api/products',{method:edit?'PUT':'POST',body}); closeModal(); toast('Producto guardado'); if(state.page==='products')renderProducts(); else if(state.page==='movement')renderMovement(); }
    catch(err){toast(err.message,'error');}
  };
}

async function importProducts(file){
  if(!file) return;
  const fd=new FormData(); fd.append('file',file);
  try{const r=await api('/api/import/products',{method:'POST',body:fd});toast(`Importación: ${r.created} creados, ${r.updated} actualizados, ${r.adjusted_stock} ajustes${r.errors.length?` · ${r.errors.length} errores`:''}`,r.errors.length?'error':'ok');renderProducts();}
  catch(err){toast(err.message,'error');}
}
async function downloadExport(url,filename){
  try{const res=await api(url);const blob=await res.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}catch(err){toast(err.message,'error');}
}

async function renderReplenishment(){
  main.innerHTML='<div class="card">Cargando reposición...</div>';
  try{
    const [items,suppliers]=await Promise.all([api('/api/replenishment'),loadSuppliers()]);
    const cats=[...new Set(items.map(x=>x.category_name).filter(Boolean))].sort();
    main.innerHTML=`<div class="page-head"><div><h1>Reposición</h1><p>Productos que llegaron al mínimo o están por debajo.</p></div></div>
      <div class="filters"><select id="repSupplier"><option value="">Todos los proveedores</option>${suppliers.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select><select id="repCategory"><option value="">Todas las categorías</option>${cats.map(c=>`<option>${esc(c)}</option>`).join('')}</select><select id="repState"><option value="all">Stock bajo y sin stock</option><option value="out">Sólo sin stock</option></select><button id="selectAllRep" class="btn btn-light">Seleccionar visibles</button><button id="generateOrder" class="btn btn-primary">GENERAR PEDIDO</button></div>
      <div id="repTable"></div>`;
    const render=()=>{
      const sid=$('#repSupplier').value, cat=$('#repCategory').value, mode=$('#repState').value;
      const filtered=items.filter(x=>(!sid||String(x.supplier_id)===sid)&&(!cat||x.category_name===cat)&&(mode!=='out'||Number(x.stock_current)<=0));
      $('#repTable').innerHTML=filtered.length?`<div class="table-wrap"><table class="table"><thead><tr><th></th><th>Producto</th><th>Proveedor</th><th>Stock</th><th>Mínimo</th><th>Objetivo</th><th>Pedir</th></tr></thead><tbody>${filtered.map(x=>`<tr><td><input class="rep-check" type="checkbox" data-id="${x.product_id}" style="width:auto"></td><td><strong>${esc(x.name)}</strong><br><small class="muted">${esc(x.barcode)}</small></td><td>${esc(x.supplier_name||'Sin proveedor')}</td><td>${qty(x.stock_current)}</td><td>${qty(x.stock_min)}</td><td>${qty(x.stock_target)}</td><td><input class="rep-qty" data-id="${x.product_id}" type="number" min="0.001" step="1" value="${qty(x.suggested_order)}" style="width:110px"></td></tr>`).join('')}</tbody></table></div>`:'<div class="card empty">No hay productos que coincidan con el filtro.</div>';
    };
    render(); $('#repSupplier').onchange=render;$('#repCategory').onchange=render;$('#repState').onchange=render;
    $('#selectAllRep').onclick=()=>$$('.rep-check').forEach(c=>c.checked=true);
    $('#generateOrder').onclick=()=>generateOrderFromSelection(items,suppliers);
  }catch(err){main.innerHTML=`<div class="alert-box danger">${esc(err.message)}</div>`;}
}

async function generateOrderFromSelection(allItems,suppliers){
  const selected=$$('.rep-check:checked').map(c=>Number(c.dataset.id));
  if(!selected.length) return toast('Seleccioná al menos un producto','error');
  const products=selected.map(id=>allItems.find(x=>x.product_id===id));
  if(products.some(x=>!x?.supplier_id)) return toast('Hay productos seleccionados sin proveedor habitual','error');
  const supplierIds=[...new Set(products.map(x=>x.supplier_id))];
  if(supplierIds.length!==1) return toast('Para generar un pedido, seleccioná productos de un solo proveedor','error');
  const supplier=suppliers.find(s=>s.id===supplierIds[0]);
  const orderItems=products.map(x=>({product_id:x.product_id,quantity:Number($(`.rep-qty[data-id="${x.product_id}"]`).value)}));
  if(orderItems.some(x=>!(x.quantity>0))) return toast('Revisá las cantidades a pedir','error');
  try{
    const r=await api('/api/orders/generate',{method:'POST',body:{supplier_id:supplierIds[0],items:orderItems}});
    openModal(`<h2>Pedido para ${esc(r.supplier_name)}</h2><p class="muted">Revisá el texto antes de enviarlo.</p><textarea id="orderMessage" class="order-message">${esc(r.message)}</textarea><div class="form-actions"><button id="copyOrder" class="btn btn-light">COPIAR MENSAJE</button>${r.whatsapp_url?'<button id="openWhatsapp" class="btn btn-primary">ABRIR WHATSAPP</button>':''}</div>`);
    $('#copyOrder').onclick=async()=>{await navigator.clipboard.writeText($('#orderMessage').value);toast('Mensaje copiado');};
    if(r.whatsapp_url) $('#openWhatsapp').onclick=()=>window.open(r.whatsapp_url,'_blank','noopener');
  }catch(err){toast(err.message,'error');}
}

async function renderHistory(){
  const suppliers=await loadSuppliers();
  main.innerHTML=`<div class="page-head"><div><h1>Historial</h1><p>Los movimientos no se eliminan del sistema.</p></div></div>
    <div class="filters"><input id="hFrom" type="date"><input id="hTo" type="date"><input id="hBarcode" placeholder="Código de barras"><select id="hType"><option value="">Todos los tipos</option>${['RETIRO','INGRESO','AJUSTE','DEVOLUCION','CORRECCION'].map(t=>`<option>${t}</option>`).join('')}</select><select id="hSupplier"><option value="">Todos los proveedores</option>${suppliers.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('')}</select></div>
    <div class="actions" style="margin-bottom:14px"><button id="loadHistory" class="btn btn-dark">Aplicar filtros</button></div><div id="historyTable"></div>`;
  $('#loadHistory').onclick=loadHistory; loadHistory();
}
async function loadHistory(){
  const p=new URLSearchParams(); if($('#hFrom')?.value)p.set('date_from',$('#hFrom').value);if($('#hTo')?.value)p.set('date_to',$('#hTo').value);if($('#hBarcode')?.value)p.set('barcode',$('#hBarcode').value);if($('#hType')?.value)p.set('movement_type',$('#hType').value);if($('#hSupplier')?.value)p.set('supplier_id',$('#hSupplier').value);
  try{const items=await api(`/api/stock/history?${p}`);$('#historyTable').innerHTML=movementTable(items);}catch(err){toast(err.message,'error');}
}

async function renderSuppliers(){
  main.innerHTML='<div class="card">Cargando proveedores...</div>';
  try{
    const suppliers=await loadSuppliers();
    main.innerHTML=`<div class="page-head"><div><h1>Proveedores</h1><p>Contactos utilizados para reposición y WhatsApp.</p></div>${isAdmin()?'<button id="newSupplier" class="btn btn-primary">+ Agregar proveedor</button>':''}</div>
      <div class="table-wrap"><table class="table"><thead><tr><th>Proveedor</th><th>Contacto</th><th>Teléfono</th><th>WhatsApp</th><th>Email</th><th>Dirección</th><th></th></tr></thead><tbody>${suppliers.map(s=>`<tr><td><strong>${esc(s.name)}</strong></td><td>${esc(s.contact_name||'-')}</td><td>${esc(s.phone||'-')}</td><td>${esc(s.whatsapp||'-')}</td><td>${esc(s.email||'-')}</td><td>${esc(s.address||'-')}</td><td>${isAdmin()?`<button class="btn btn-light edit-supplier" data-id="${s.id}">Editar</button>`:''}</td></tr>`).join('')}</tbody></table></div>`;
    if(isAdmin()){
      $('#newSupplier').onclick=()=>openSupplierForm();
      $$('.edit-supplier').forEach(b=>b.onclick=()=>openSupplierForm(suppliers.find(s=>s.id===Number(b.dataset.id))));
    }
  }catch(err){main.innerHTML=`<div class="alert-box danger">${esc(err.message)}</div>`;}
}
function openSupplierForm(s=null){
  openModal(`<h2>${s?'Editar':'Agregar'} proveedor</h2><form id="supplierForm"><div class="form-grid">
    <label>Nombre<input id="sfName" value="${esc(s?.name||'')}" required></label><label>Contacto<input id="sfContact" value="${esc(s?.contact_name||'')}"></label><label>Teléfono<input id="sfPhone" value="${esc(s?.phone||'')}"></label><label>WhatsApp<input id="sfWhatsapp" value="${esc(s?.whatsapp||'')}" placeholder="54911..."></label><label>Email<input id="sfEmail" type="email" value="${esc(s?.email||'')}"></label><label>Dirección<input id="sfAddress" value="${esc(s?.address||'')}"></label><label class="full">Observaciones<textarea id="sfNotes">${esc(s?.notes||'')}</textarea></label>
    </div><div class="form-actions"><button class="btn btn-primary" type="submit">Guardar</button></div></form>`);
  $('#supplierForm').onsubmit=async e=>{e.preventDefault();const body={name:$('#sfName').value.trim(),contact_name:$('#sfContact').value||null,phone:$('#sfPhone').value||null,whatsapp:$('#sfWhatsapp').value||null,email:$('#sfEmail').value||null,address:$('#sfAddress').value||null,notes:$('#sfNotes').value||null};try{await api(s?`/api/suppliers/${s.id}`:'/api/suppliers',{method:s?'PUT':'POST',body});closeModal();toast('Proveedor guardado');renderSuppliers();}catch(err){toast(err.message,'error');}};
}

(async function init(){
  if(state.token){
    try{state.user=await api('/api/auth/me');localStorage.setItem('ferreteria_user',JSON.stringify(state.user));showApp();}
    catch{showLogin();}
  }else showLogin();
})();
