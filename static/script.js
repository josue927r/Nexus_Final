const fileIbotInput = document.getElementById('file-ibot');
// const fileTbInput = document.getElementById('file-tb'); // Removed
const processBtn = document.getElementById('process-btn');
const resultsSection = document.getElementById('results-section');


// Initialize Date Input with Today - REMOVED (Element deleted from DOM)
document.addEventListener('DOMContentLoaded', () => {
    // const today = new Date().toISOString().split('T')[0];
    // const dateInput = document.getElementById('report-date');
    // if (dateInput) dateInput.value = today;
});

// --- VOUCHER CALCULATION LOGIC ---
const voucherTable = document.getElementById('voucher-table');
const grandTotalSistema = document.getElementById('grand-total-sistema');
const grandTotalReal = document.getElementById('grand-total-real');
const grandTotalDiff = document.getElementById('grand-total-diff');

// --- HELPERS PARA POSICIÓN DEL CURSOR ---
// Obtiene cuántos caracteres "significativos" (dígitos o +) hay antes del cursor
function getCursorState(input) {
    const cursor = input.selectionStart;
    const val = input.value;
    const prefix = val.substring(0, cursor);
    return (prefix.match(/[0-9+]/g) || []).length;
}

// Restaura el cursor a la posición correcta basada en los caracteres significativos
function restoreCursorState(input, targetCount) {
    const val = input.value;
    let count = 0;
    let pos = 0;

    // Recorrer el nuevo valor para encontrar donde se cumple el conteo
    while (pos < val.length) {
        if (/[0-9+]/.test(val[pos])) {
            count++;
        }
        // Si ya pasamos el target, significa que la posición anterior era la correcta
        // Pero queremos estar DESPUÉS del caracter targetCount-ésimo
        if (count > targetCount) {
            break;
        }
        pos++;
    }
    input.setSelectionRange(pos, pos);
}

// Función para limpiar formato ($ y puntos)
function cleanNumber(value) {
    if (!value) return 0;
    return parseInt(value.replace(/\D/g, '')) || 0;
}

// Función para formatear moneda
function formatCLP(value) {
    return '$ ' + new Intl.NumberFormat('es-CL').format(value);
}

// Función para formatear INPUT mientras se escribe
function formatCurrencyInput(e) {
    const input = e.target;
    // 1. Guardar estado del cursor (cuántos dígitos hay antes)
    const cursorState = getCursorState(input);

    let value = input.value.replace(/\D/g, '');
    if (value === "") {
        input.value = "";
        return;
    }
    input.value = formatCLP(value);

    // 2. Restaurar cursor
    restoreCursorState(input, cursorState);
}

function calculateTable() {
    let totalSist = 0;
    let totalReal = 0;

    // Iterar por cada fila del cuerpo de la tabla
    const rows = voucherTable.querySelectorAll('tbody tr');

    rows.forEach(row => {
        const inputSist = row.querySelector('.v-sistema');
        const inputReal = row.querySelector('.v-real');
        const cellDiff = row.querySelector('.v-diff');

        const valSist = cleanNumber(inputSist.value);
        const valReal = cleanNumber(inputReal.value);

        // Calcular Diferencia Fila
        const diff = valReal - valSist;
        cellDiff.textContent = formatCLP(diff);

        // Colores para diferencia fila
        if (diff === 0) cellDiff.style.color = 'var(--success)';
        else if (diff < 0) cellDiff.style.color = 'var(--danger)';
        else cellDiff.style.color = 'var(--warning)';

        // Acumular Totales
        totalSist += valSist;
        totalReal += valReal;
    });

    // Actualizar Footer (Totales Globales)
    grandTotalSistema.textContent = formatCLP(totalSist);
    grandTotalReal.textContent = formatCLP(totalReal);

    const globalDiff = totalReal - totalSist;
    grandTotalDiff.textContent = formatCLP(globalDiff);

    // Colores Total Global
    if (globalDiff === 0) grandTotalDiff.style.color = 'var(--success)';
    else if (globalDiff < 0) grandTotalDiff.style.color = 'var(--danger)';
    else grandTotalDiff.style.color = 'var(--warning)';
}

// Asignar listeners a todos los inputs de la tabla
document.querySelectorAll('.currency-input').forEach(input => {
    input.addEventListener('input', (e) => {
        formatCurrencyInput(e);
        calculateTable();
    });
});

// Event Listeners for file selection styling
[fileIbotInput].forEach(input => {
    if (!input) return;
    input.addEventListener('change', () => {
        const label = document.getElementById(`${input.id}-label`);
        if (input.files.length > 0) {
            label.textContent = `✅ ${input.files[0].name}`;
            label.classList.add('ready');
        } else {
            label.textContent = 'Pendiente selección...';
            label.classList.remove('ready');
        }
    });
});

processBtn.addEventListener('click', async () => {
    if (fileIbotInput.files.length === 0) {
        alert("Por favor selecciona el archivo de iBot.");
        return;
    }

    // UI Loading State
    processBtn.disabled = true;
    processBtn.innerHTML = '<div class="spinner"></div> Procesando...';
    resultsSection.style.display = 'none';

    const formData = new FormData();
    formData.append('file_ibot', fileIbotInput.files[0]);

    // Optional Transbank (if element exists and has file)
    const fileTbInput = document.getElementById('file-tb');
    if (fileTbInput && fileTbInput.files.length > 0) {
        formData.append('file_transbank', fileTbInput.files[0]);
    }

    // Send Voucher data (Calculated Totals)
    const granSist = cleanNumber(document.getElementById('grand-total-sistema').textContent);
    const granReal = cleanNumber(document.getElementById('grand-total-real').textContent);

    formData.append('voucher_sistema', granSist);
    formData.append('voucher_real', granReal);

    // Send Shift Time Filters - MODIFICADO: UI Removed, auto-sending defaults
    const shiftStart = "";
    const shiftEnd = "";
    // Default to today for pivot table compatibility
    const reportDate = new Date().toISOString().split('T')[0];

    formData.append('shift_start', shiftStart);
    formData.append('shift_end', shiftEnd);
    formData.append('fecha_reporte', reportDate);

    try {
        const response = await fetch('/conciliar-caja/', {
            method: 'POST',
            body: formData
        });

        if (response.status === 401) {
            alert("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.");
            window.location.href = '/login';
            return;
        }

        if (!response.ok) {
            let errorMessage = `Error del servidor: ${response.statusText}`;
            try {
                const errorData = await response.json();
                if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
            } catch (e) {
                // Si no es JSON, mantenemos el mensaje genérico
            }
            throw new Error(errorMessage);
        }

        const data = await response.json();
        renderResults(data);
        resultsSection.style.display = 'block';

    } catch (error) {
        alert("Hubo un error al procesar los archivos: " + error.message);
        console.error(error);
    } finally {
        processBtn.disabled = false;
        processBtn.textContent = 'Analizar Cuadratura 🚀';
    }
});

function formatMoney(amount) {
    return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(amount);
}

function renderResults(data) {
    const resumen = data.resumen_general;
    const detalle = data.analisis_detallado;
    const voucher = data.voucher_analisis;
    const alertasInternas = data.analisis_interno || [];

    const resultsContainer = document.getElementById('results-section');

    // -1. Internal Analysis (New! - Critico)
    if (alertasInternas.length > 0) {
        let internalCard = document.getElementById('internal-alert-card');
        if (!internalCard) {
            internalCard = document.createElement('div');
            internalCard.id = 'internal-alert-card';
            internalCard.className = 'upload-card';
            internalCard.style.marginBottom = '20px';
            internalCard.style.borderLeft = '5px solid #ef4444'; // Red
            internalCard.style.backgroundColor = '#fef2f2'; // Light Red BG
            resultsContainer.insertBefore(internalCard, resultsContainer.firstChild);
        }

        internalCard.innerHTML = `
            <div style="text-align: left; padding-bottom: 12px; border-bottom: 1px solid rgba(239, 68, 68, 0.15); margin-bottom: 12px;">
                <h3 style="color: #991B1B; margin: 0 0 6px 0; display: flex; align-items: center; gap: 8px; font-size: 1.2rem;">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" style="width: 24px; height: 24px; color: #DC2626;">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                    </svg>
                    Inconsistencia Interna Detectada
                </h3>
                <p style="color: #7F1D1D; margin: 0; font-size: 0.9rem; line-height: 1.4; opacity: 0.9;">
                    Existen montos en el <strong>detalle</strong> que Excel no sumó en la <strong>Tabla Dinámica</strong>. 
                </p>
            </div>
            
            <div style="display: grid; gap: 8px;">
                ${alertasInternas.map(a => {
            const montoMatch = a.mensaje.match(/(\$[0-9,.]+)/);
            const monto = montoMatch ? montoMatch[0] : '???';

            let icon = '📉';
            let title = 'Falta en Ibotecario';
            let desc = 'Está en el detalle pero no en el resumen.';

            if (a.mensaje.includes('NO en el detalle')) {
                icon = '📈';
                title = 'Falta en Transbank';
                desc = 'Está en el resumen pero no en el detalle.';
            }

            return `
                        <div style="background: rgba(255, 255, 255, 0.6); border: 1px solid rgba(239, 68, 68, 0.15); border-radius: 8px; padding: 10px 14px; display: flex; align-items: center; justify-content: space-between;">
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="background: #FEF2F2; color: #DC2626; width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; border: 1px solid rgba(239,68,68,0.1);">
                                    ${icon}
                                </div>
                                <div>
                                    <div style="font-weight: 700; color: #991B1B; font-size: 1rem;">${monto}</div>
                                    <div style="font-size: 0.75rem; color: #B91C1C; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">${title}</div>
                                </div>
                            </div>
                            <div style="font-size: 0.8rem; color: #7F1D1D; max-width: 45%; text-align: right; opacity: 0.85;">
                                ${desc}
                            </div>
                        </div>
                    `;
        }).join('')}
            </div>
        `;
    } else {
        // Limpiar si no hay errores en nueva corrida
        const existing = document.getElementById('internal-alert-card');
        if (existing) existing.remove();
    }

    // 0. Voucher Analysis (New!)
    if (voucher && voucher.mensaje !== "No se ingresaron datos del voucher.") {
        const resultsContainer = document.getElementById('results-section');
        let voucherCard = document.getElementById('voucher-result-card');

        if (!voucherCard) {
            voucherCard = document.createElement('div');
            voucherCard.id = 'voucher-result-card';
            voucherCard.className = 'upload-card';
            voucherCard.style.marginBottom = '20px';
            voucherCard.style.borderLeft = '5px solid var(--primary)';
            resultsContainer.insertBefore(voucherCard, resultsContainer.firstChild);
        }

        voucherCard.innerHTML = `
            <h3>🔍 Análisis vs Voucher</h3>
            <div style="display:flex; justify-content:space-around; margin:15px 0;">
                 <div>
                    <small>Tu Diferencia (Voucher)</small>
                    <div style="font-weight:bold; font-size:1.2rem">${formatMoney(voucher.diferencia_declarada)}</div>
                 </div>
                 <div>
                    <small>Explicado por Archivos</small>
                    <div style="font-weight:bold; font-size:1.2rem">${formatMoney(voucher.diferencia_encontrada_archivos)}</div>
                 </div>
            </div>
            <div style="background:#F3F4F6; padding:10px; border-radius:8px; font-weight:600;">
                ${voucher.mensaje}
            </div>
        `;
    }

    // 1. Resumen Cards
    document.getElementById('total-sistema').textContent = formatMoney(resumen.total_declarado_sistema);
    document.getElementById('total-banco').textContent = formatMoney(resumen.total_real_banco);

    const diffEl = document.getElementById('diferencia-neta');
    diffEl.textContent = formatMoney(resumen.diferencia_neta);
    diffEl.style.color = resumen.diferencia_neta === 0 ? 'var(--success)' : 'var(--danger)';






}

// --- LOGICA CAJA AUXILIAR ---

const btnSaveAux = document.getElementById('btn-save-aux');

// --- DYNAMIC ROWS LOGIC ---
const addConceptBtn = document.getElementById('add-concept-btn');

addConceptBtn.addEventListener('click', () => {
    addConceptRow();
});

function addConceptRow() {
    const tbody = voucherTable.querySelector('tbody');
    const tr = document.createElement('tr');

    tr.innerHTML = `
        <td><input type="text" class="form-input" placeholder="Nombre Concepto (ej: Uber)"></td>
        <td><input type="text" class="form-input currency-input v-sistema" placeholder="$0"></td>
        <td><input type="text" class="form-input currency-input v-real" placeholder="$0"></td>
        <td class="v-diff" style="font-weight: bold;">$ 0</td>
        <td style="text-align: center;">
            <button class="btn-delete" title="Eliminar">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" style="width:16px;height:16px;">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
            </button>
        </td>
    `;

    // Add event listeners to new inputs
    const inputs = tr.querySelectorAll('.currency-input');
    inputs.forEach(input => {
        input.addEventListener('input', (e) => {
            formatCurrencyInput(e);
            calculateTable();
        });
    });

    // Add event listener to delete button
    const deleteBtn = tr.querySelector('.btn-delete');
    deleteBtn.addEventListener('click', () => {
        tr.remove();
        calculateTable();
    });

    tbody.appendChild(tr);
}

// --- DARK MODE LOGIC ---
const toggleBtn = document.getElementById('theme-toggle');
const iconSun = document.getElementById('icon-sun');
const iconMoon = document.getElementById('icon-moon');
const htmlEl = document.documentElement;

// Function to update UI based on theme
function updateThemeUI(theme) {
    if (theme === 'dark') {
        iconSun.style.display = 'block';
        iconMoon.style.display = 'none';
        htmlEl.setAttribute('data-theme', 'dark');
    } else {
        iconSun.style.display = 'none';
        iconMoon.style.display = 'block';
        htmlEl.removeAttribute('data-theme');
    }
}

// Load saved preference
const savedTheme = localStorage.getItem('theme') || 'light';
updateThemeUI(savedTheme);

toggleBtn.addEventListener('click', () => {
    const currentTheme = htmlEl.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    updateThemeUI(newTheme);
    localStorage.setItem('theme', newTheme);
});

// --- TAB LOGIC ---
function switchTab(tabId) {
    // Hide all contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    // Deselect all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show target content
    document.getElementById(tabId).classList.add('active');
    // Select target button (can be a, button, etc)
    const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    if (targetBtn) {
        targetBtn.classList.add('active');
    }
}


// Función para formatear INPUT complejo (permite sumas con +)
function formatComplexCurrencyInput(e) {
    const input = e.target;
    // 1. Guardar estado cursor
    const cursorState = getCursorState(input);

    // 2. Limpiar: dejar solo dígitos y +
    let raw = input.value.replace(/[^0-9+]/g, '');

    if (!raw) {
        input.value = "";
        return;
    }

    // 3. Dividir por +
    let parts = raw.split('+');

    // 4. Formatear cada parte (SIN el signo $)
    let formattedParts = parts.map(part => {
        if (part === "") return ""; // Caso "100+" -> el segundo es vacío
        if (!part.match(/\d/)) return ""; // Si es solo basura (?)
        return new Intl.NumberFormat('es-CL').format(parseInt(part));
    });

    // 5. Unir y agregar UN SOLO signo $ al principio
    input.value = '$ ' + formattedParts.join(" + ");

    // 6. Restaurar cursor
    restoreCursorState(input, cursorState);
}

// --- BRANCH RECONCILIATION LOGIC ---
const branchesContainer = document.getElementById('branches-container');
const addBranchBtn = document.getElementById('add-branch-btn');
const btnCalcBranches = document.getElementById('btn-calc-branches');
const branchesSummary = document.getElementById('branches-summary');

// Initial Branches
const initialBranches = ["EJERCITO", "SAN CARLOS", "LA PINTANA", "VIOLETA PARRA", "GENERAL ARRIAGADA"];

function createBranchRow(name = "", containerElement = branchesContainer) {
    const div = document.createElement('div');
    div.className = 'branch-item';
    div.style.display = 'grid';
    div.style.gridTemplateColumns = '1.5fr 2.5fr 2.5fr 2.5fr 1fr 40px';
    div.style.gap = '10px';
    div.style.alignItems = 'center';
    div.style.marginBottom = '10px';

    div.innerHTML = `
        <div class="input-group" style="margin-bottom: 0;">
            <input type="text" class="form-input branch-name" placeholder="Nombre Sucursal" value="${name}">
        </div>
        <div class="input-group" style="margin-bottom: 0;">
            <input type="text" class="form-input branch-debit" placeholder="Débito (ej: 100+200)">
        </div>
        <div class="input-group" style="margin-bottom: 0;">
             <input type="text" class="form-input branch-credit" placeholder="Crédito (ej: 500)">
        </div>
        <div class="input-group" style="margin-bottom: 0;">
             <input type="text" class="form-input branch-sales" placeholder="Venta Decl. (ej: 800)">
        </div>
        <div class="branch-diff-cell" style="font-weight: bold; text-align: center; color: var(--text-muted); display: flex; align-items: center; justify-content: center;">
            -
        </div>
        <button class="btn-delete" title="Eliminar fila" onclick="this.parentElement.remove()" style="margin: auto;">
             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" style="width:16px;height:16px;">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
        </button>
    `;

    // Attach event listeners for currency formatting
    div.querySelectorAll('.branch-debit, .branch-credit, .branch-sales').forEach(input => {
        input.addEventListener('input', formatComplexCurrencyInput);
    });

    containerElement.appendChild(div);
}

// Initialize branches if container exists (to avoid errors if tab is not present in DOM yet)
if (branchesContainer) {
    initialBranches.forEach(branch => createBranchRow(branch, branchesContainer));

    const cretaContainer = document.getElementById('creta-container');
    if (cretaContainer) {
        createBranchRow("CRETA", cretaContainer);
    }
}

if (addBranchBtn) {
    addBranchBtn.addEventListener('click', () => createBranchRow("", branchesContainer));
}

if (btnCalcBranches) {
    btnCalcBranches.addEventListener('click', async () => {
        const items = [];
        const rows = branchesContainer.querySelectorAll('.branch-item');

        rows.forEach(row => {
            const name = row.querySelector('.branch-name').value;
            const debit = row.querySelector('.branch-debit').value;
            const credit = row.querySelector('.branch-credit').value;
            const sales = row.querySelector('.branch-sales').value;

            if (name) {
                items.push({
                    name: name,
                    debit: debit,
                    credit: credit,
                    sales_declared: sales
                });
            }
        });

        try {
            btnCalcBranches.disabled = true;
            btnCalcBranches.textContent = "Calculando...";

            const response = await fetch('/calculate-branches', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(items)
            });

            if (response.status === 401) {
                alert("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.");
                window.location.href = '/login';
                return;
            }

            if (!response.ok) throw new Error("Error en cálculo");

            const data = await response.json();

            // Actualizar los inputs con los valores sumados y las diferencias en la misma fila
            rows.forEach((row, index) => {
                const branchData = data.branches[index];
                if (branchData && row.querySelector('.branch-name').value) {
                    row.querySelector('.branch-debit').value = formatMoney(branchData.debit);
                    row.querySelector('.branch-credit').value = formatMoney(branchData.credit);
                    row.querySelector('.branch-sales').value = formatMoney(branchData.sales_declared);
                    
                    const diffCell = row.querySelector('.branch-diff-cell');
                    diffCell.textContent = formatMoney(branchData.difference);
                    diffCell.style.color = branchData.difference === 0 ? 'var(--success)' : 'var(--danger)';
                }
            });

            renderBranchResults(data);
            branchesSummary.style.display = 'grid'; // Utilizamos grid para el summary-grid

        } catch (e) {
            alert("Error: " + e.message);
        } finally {
            btnCalcBranches.disabled = false;
            btnCalcBranches.textContent = "Calcular Cuadratura 🚀";
        }
    });
}

function renderBranchResults(data) {
    document.getElementById('global-debit').textContent = formatMoney(data.global_debit);
    document.getElementById('global-credit').textContent = formatMoney(data.global_credit);
    document.getElementById('global-sales').textContent = formatMoney(data.global_sales);

    const diffEl = document.getElementById('global-diff');
    diffEl.textContent = formatMoney(data.global_difference);
    diffEl.style.color = data.global_difference === 0 ? 'var(--success)' :
        data.global_difference > 0 ? 'var(--warning)' : 'var(--danger)';
}

const btnCalcCreta = document.getElementById('btn-calc-creta');
if (btnCalcCreta) {
    btnCalcCreta.addEventListener('click', async () => {
        const cretaContainer = document.getElementById('creta-container');
        const items = [];
        const rows = cretaContainer.querySelectorAll('.branch-item');

        rows.forEach(row => {
            const name = row.querySelector('.branch-name').value;
            const debit = row.querySelector('.branch-debit').value;
            const credit = row.querySelector('.branch-credit').value;
            const sales = row.querySelector('.branch-sales').value;

            if (name) {
                items.push({ name, debit, credit, sales_declared: sales });
            }
        });

        try {
            btnCalcCreta.disabled = true;
            btnCalcCreta.textContent = "Calculando...";

            const response = await fetch('/calculate-branches', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(items)
            });

            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }

            if (!response.ok) throw new Error("Error en cálculo");

            const data = await response.json();

            rows.forEach((row, index) => {
                const branchData = data.branches[index];
                if (branchData && row.querySelector('.branch-name').value) {
                    row.querySelector('.branch-debit').value = formatMoney(branchData.debit);
                    row.querySelector('.branch-credit').value = formatMoney(branchData.credit);
                    row.querySelector('.branch-sales').value = formatMoney(branchData.sales_declared);
                    
                    const diffCell = row.querySelector('.branch-diff-cell');
                    diffCell.textContent = formatMoney(branchData.difference);
                    diffCell.style.color = branchData.difference === 0 ? 'var(--success)' : 'var(--danger)';
                }
            });

            renderCretaResults(data);
            const cretaSummaryCont = document.getElementById('creta-summary-container');
            if (cretaSummaryCont) cretaSummaryCont.style.display = 'block';

        } catch (e) {
            alert("Error: " + e.message);
        } finally {
            btnCalcCreta.disabled = false;
            btnCalcCreta.textContent = "Calcular Creta 🚀";
        }
    });
}

function renderCretaResults(data) {
    document.getElementById('creta-debit').textContent = formatMoney(data.global_debit);
    document.getElementById('creta-credit').textContent = formatMoney(data.global_credit);
    document.getElementById('creta-sales').textContent = formatMoney(data.global_sales);
    
    const diffEl = document.getElementById('creta-diff');
    diffEl.textContent = formatMoney(data.global_difference);
    diffEl.style.color = data.global_difference === 0 ? 'var(--success)' :
        data.global_difference > 0 ? 'var(--warning)' : 'var(--danger)';
}

// --- SIDEBAR LOGIC ---
function toggleSidebar() {
    const sidebar = document.getElementById('app-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    
    if (sidebar) {
        if (window.innerWidth <= 900) {
            sidebar.classList.toggle('open');
            if (overlay) overlay.classList.toggle('active');
        } else {
            sidebar.classList.toggle('closed');
        }
    }
}

// Add event listener to sidebar links to close sidebar on mobile when clicked
document.addEventListener('DOMContentLoaded', () => {
    const sidebarLinks = document.querySelectorAll('.sidebar-link');
    sidebarLinks.forEach(link => {
        link.addEventListener('click', () => {
            const sidebar = document.getElementById('app-sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            if (sidebar && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            }
        });
    });
});
