#!/usr/bin/env python3
"""
Script para visualizar o grafo de máquina de estados do NPC Agent.
Lê o wiring.py e gera uma imagem do grafo em estilo "Airflow DAG".

Uso:
    python visualize_graph.py
"""

import re
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


# ----------------------------------------------------------------------
# PARSE DO WIRING
# ----------------------------------------------------------------------
def parse_wiring_file(file_path: Path) -> Dict:
    """Parseia o arquivo wiring.py para extrair informações do grafo."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extrai nós
    nodes: List[str] = []
    node_pattern = r'g\.add_node\("([^"]+)",\s*([^)]+)\)'
    for match in re.finditer(node_pattern, content):
        node_name = match.group(1)
        nodes.append(node_name)

    # Extrai arestas simples
    edges: List[Tuple[str, str, str | None]] = []
    edge_pattern = r'g\.add_edge\("([^"]+)",\s*"([^"]+)"\)'
    for match in re.finditer(edge_pattern, content):
        source = match.group(1)
        target = match.group(2)
        edges.append((source, target, None))  # None = aresta simples

    # Extrai arestas condicionais
    conditional_pattern = r'g\.add_conditional_edges\("([^"]+)",\s*[^,]+,\s*\{([^}]+)\}\)'
    for match in re.finditer(conditional_pattern, content):
        source = match.group(1)
        conditions = match.group(2)
        # Parseia as condições: "world_model": "world_model", "dialogue": "dialogue"
        cond_pattern = r'"([^"]+)":\s*"([^"]+)"'
        for cond_match in re.finditer(cond_pattern, conditions):
            condition = cond_match.group(1)
            target = cond_match.group(2)
            edges.append((source, target, condition))

    # Extrai ponto de entrada
    entry_point = None
    entry_pattern = r'g\.set_entry_point\("([^"]+)"\)'
    match = re.search(entry_pattern, content)
    if match:
        entry_point = match.group(1)

    return {
        'nodes': nodes,
        'edges': edges,
        'entry_point': entry_point,
    }


# ----------------------------------------------------------------------
# LAYOUT E DESENHO COM MATPLOTLIB
# ----------------------------------------------------------------------
def build_full_graph(graph_data: Dict) -> tuple[list[str], list[tuple[str, str, str | None]]]:
    """Adiciona START/END e garante conexão para END."""
    nodes = list(graph_data['nodes'])
    edges = list(graph_data['edges'])
    entry_point = graph_data['entry_point']

    full_nodes: List[str] = []
    if 'START' not in full_nodes:
        full_nodes.append('START')
    full_nodes.extend(nodes)
    if 'END' not in full_nodes:
        full_nodes.append('END')

    full_edges: List[Tuple[str, str, str | None]] = []

    # Aresta START -> entry_point
    if entry_point:
        full_edges.append(('START', entry_point, None))

    # Arestas do wiring
    full_edges.extend(edges)

    # Conecta último nó ao END se não houver caminho explícito
    last_node = None
    source_nodes = {s for s, _, _ in edges}
    for node in reversed(nodes):
        if node not in source_nodes:
            last_node = node
            break
    if not last_node and nodes:
        last_node = nodes[-1]

    if last_node:
        has_end_edge = any(s == last_node and t == 'END' for s, t, _ in edges)
        if not has_end_edge:
            full_edges.append((last_node, 'END', None))

    return full_nodes, full_edges


def compute_layout(nodes: List[str], edges: List[Tuple[str, str, str | None]]) -> Dict[str, tuple[float, float]]:
    """
    Calcula posição (x, y) de cada nó em estilo DAG horizontal
    usando BFS a partir de START (se existir).
    """
    # BFS para profundidades
    depth = {node: None for node in nodes}

    if 'START' in nodes:
        start_node = 'START'
    else:
        # usa o primeiro como "start" caso não exista
        start_node = nodes[0]

    q = deque()
    depth[start_node] = 0
    q.append(start_node)

    while q:
        u = q.popleft()
        for s, t, _ in edges:
            if s == u and depth.get(t) is None:
                depth[t] = depth[u] + 1
                q.append(t)

    # Nós não alcançáveis: joga para depois
    max_depth = max(d for d in depth.values() if d is not None) if depth.values() else 0
    for node in nodes:
        if depth[node] is None:
            max_depth += 1
            depth[node] = max_depth

    # Agrupa por camada
    layers: Dict[int, List[str]] = {}
    for node, d in depth.items():
        layers.setdefault(d, []).append(node)

    # Ordena camadas
    sorted_layers = sorted(layers.items(), key=lambda x: x[0])

    # Define posições com espaçamento bem aumentado
    x_spacing = 15.0  # Aumentado significativamente de 4.5 para 7.0
    y_spacing = 12.0  # Aumentado significativamente de 2.5 para 4.0
    positions: Dict[str, tuple[float, float]] = {}

    for i, (_, layer_nodes) in enumerate(sorted_layers):
        n = len(layer_nodes)
        # centraliza verticalmente ao redor de 0
        y_start = (n - 1) * y_spacing / 2.0 if n > 1 else 0
        for idx, node in enumerate(layer_nodes):
            x = i * x_spacing
            y = y_start - idx * y_spacing
            positions[node] = (x, y)

    return positions


def draw_graph_matplotlib(graph_data: Dict, output_path: Path):
    """Desenha o grafo usando apenas matplotlib, estilo 'Airflow DAG'."""
    nodes, edges = build_full_graph(graph_data)
    positions = compute_layout(nodes, edges)

    # Calcula limites do layout
    if not positions:
        print("⚠️  Nenhuma posição calculada!")
        return

    x_coords = [pos[0] for pos in positions.values()]
    y_coords = [pos[1] for pos in positions.values()]

    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)

    # Adiciona margens (aumentadas para acomodar maior espaçamento)
    x_margin = 12.0  # Aumentado de 3.0 para 4.0
    y_margin = 9.0  # Aumentado de 2.0 para 3.0
    x_range = (x_max - x_min) + 2 * x_margin
    y_range = (y_max - y_min) + 2 * y_margin

    # Calcula tamanho da figura mantendo proporção
    base_width = 30
    base_height = 20
    aspect_ratio = x_range / y_range if y_range > 0 else 1.0

    if aspect_ratio > base_width / base_height:
        fig_width = base_width
        fig_height = base_width / aspect_ratio
    else:
        fig_width = base_height * aspect_ratio
        fig_height = base_height

    # Limites mínimos e máximos (aumentados para acomodar maior espaçamento)
    fig_width = max(16, min(fig_width, 30))  # Aumentado de 12-24 para 16-30
    fig_height = max(10, min(fig_height, 20))  # Aumentado de 8-16 para 10-20

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    # Estilo dos nós (ajustado para caber melhor)
    node_width = 8.0  # Aumentado de 2.0 para 2.8
    node_height = 1.5  # Aumentado de 0.8 para 1.0

    def node_color(name: str) -> str:
        # START verde claro, END vermelho claro, demais verde suave
        if name == 'START':
            return '#d5f5e3'  # verde bem claro
        if name == 'END':
            return '#f5b7b1'  # vermelho claro
        # heurística opcional: se nome tiver "error" ou "fail", pinta de vermelho
        lowered = name.lower()
        if 'error' in lowered or 'fail' in lowered or 'explode' in lowered:
            return '#f1948a'  # vermelho mais forte
        return '#abebc6'      # verde claro (tipo tasks OK)

    # Desenha nós (retângulos arredondados)
    for node in nodes:
        cx, cy = positions[node]
        x = cx - node_width / 2.0
        y = cy - node_height / 2.0

        rect = FancyBboxPatch(
            (x, y),
            node_width,
            node_height,
            boxstyle="round,pad=0.2",  # Reduzido de 0.3 para 0.2 para mais espaço interno
            linewidth=1.5,
            edgecolor='#4d5656',
            facecolor=node_color(node)
        )
        ax.add_patch(rect)
        ax.text(
            cx,
            cy,
            node,
            ha='center',
            va='center',
            fontsize=9,  # Reduzido de 10 para 9 para garantir que caiba
            fontweight='normal',
            family='sans-serif',
            color='#1b2631'
        )

    # Desenha arestas (setas com cor que contrasta)
    for source, target, condition in edges:
        x1, y1 = positions[source]
        x2, y2 = positions[target]

        # começa na borda direita do nó de origem e termina na borda esquerda do destino
        start = (x1 + node_width / 2.0, y1)
        end = (x2 - node_width / 2.0, y2)

        # Define cor baseada no tipo de aresta
        if condition:
            # Arestas condicionais em laranja/vermelho
            edge_color = '#e74c3c'  # vermelho vibrante
            edge_width = 2.0
            edge_style = 'dashed'
        else:
            # Arestas simples em azul escuro
            edge_color = '#2c3e50'  # azul escuro/grafite
            edge_width = 2.5
            edge_style = 'solid'

        arrow = FancyArrowPatch(
            start,
            end,
            arrowstyle='->',  # Seta mais visível
            mutation_scale=20,  # Seta maior
            linewidth=edge_width,
            color=edge_color,
            linestyle=edge_style,
            connectionstyle="arc3,rad=0.0",
            zorder=1  # Arestas atrás dos nós
        )
        ax.add_patch(arrow)

        # Adiciona label para arestas condicionais
        if condition:
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0

            # Calcula a direção da seta para posicionar o label de forma inteligente
            dx = x2 - x1
            dy = y2 - y1
            angle = abs(dy / dx) if dx != 0 else 1.0

            # Para setas mais horizontais, coloca o label acima; para verticais, ao lado
            if angle < 0.5:  # Seta mais horizontal
                offset_x = 0.0
                offset_y = 0.6  # Mais acima para evitar sobreposição
            elif angle > 2.0:  # Seta mais vertical
                offset_x = 0.5 if dx > 0 else -0.5  # Ao lado direito ou esquerdo
                offset_y = 0.0
            else:  # Seta diagonal
                offset_x = 0.3 if dx > 0 else -0.3
                offset_y = 0.4

            ax.text(
                mid_x + offset_x,
                mid_y + offset_y,
                condition,
                ha='center',
                va='bottom',
                fontsize=7,
                color=edge_color,
                bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor=edge_color, alpha=0.95, linewidth=1.2),
                zorder=2
            )

    # Define limites do eixo com margens
    ax.set_xlim(x_min - x_margin, x_max + x_margin)
    ax.set_ylim(y_min - y_margin, y_max + y_margin)
    ax.set_aspect('equal')
    ax.axis('off')

    # Ajusta layout com padding
    plt.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.05)

    fig.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    print(f"✓ Grafo salvo em: {output_path}")


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def main():
    """Função principal."""
    script_dir = Path(__file__).parent
    wiring_file = script_dir / 'graph' / 'wiring.py'
    output_file = script_dir / 'graph_visualization.png'

    if not wiring_file.exists():
        print(f"❌ Erro: Arquivo não encontrado: {wiring_file}")
        sys.exit(1)

    print(f"📖 Lendo: {wiring_file}")
    graph_data = parse_wiring_file(wiring_file)

    print(f"📊 Nós encontrados: {len(graph_data['nodes'])}")
    print(f"   {', '.join(graph_data['nodes'])}")
    print(f"🔗 Arestas encontradas: {len(graph_data['edges'])}")
    print(f"🚪 Ponto de entrada: {graph_data['entry_point']}")

    print("🎨 Gerando visualização com matplotlib...")
    draw_graph_matplotlib(graph_data, output_file)


if __name__ == '__main__':
    main()
