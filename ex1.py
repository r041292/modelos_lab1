from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


st.set_page_config(page_title="Dashboard Retail Alimentos", layout="wide")

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

CATEGORY_COLS = [
	"units_carnes",
	"units_verduras",
	"units_frutas",
	"units_lacteos",
	"units_bebidas",
]


def load_data() -> pd.DataFrame:
	csv_path = Path(__file__).with_name("retail_tienda_alimentos.csv")
	if not csv_path.exists():
		st.error(f"No se encontró el archivo: {csv_path.name}")
		st.stop()

	df = pd.read_csv(csv_path)
	df["date"] = pd.to_datetime(df["date"], errors="coerce")
	df = df.dropna(subset=["date"])
	df["month"] = df["date"].dt.to_period("M").astype(str)
	return df


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
	st.sidebar.header("Filtros")

	day_options = [d for d in DAY_ORDER if d in set(df["day_of_week"].dropna().unique())]
	selected_days = st.sidebar.multiselect(
		"day_of_week",
		options=day_options,
		default=day_options,
	)

	season_options = sorted(df["season"].dropna().unique().tolist())
	selected_seasons = st.sidebar.multiselect(
		"season",
		options=season_options,
		default=season_options,
	)

	month_options = sorted(df["month"].dropna().unique().tolist())
	selected_months = st.sidebar.multiselect(
		"Meses (agrupación por date)",
		options=month_options,
		default=month_options,
	)

	min_date = df["date"].min().date()
	max_date = df["date"].max().date()
	date_range = st.sidebar.slider(
		"Rango de fechas (date)",
		min_value=min_date,
		max_value=max_date,
		value=(min_date, max_date),
		format="YYYY-MM-DD",
	)

	filtered = df[
		df["day_of_week"].isin(selected_days)
		& df["season"].isin(selected_seasons)
		& df["month"].isin(selected_months)
		& (df["date"].dt.date >= date_range[0])
		& (df["date"].dt.date <= date_range[1])
	].copy()

	return filtered


def get_theme_settings() -> dict:
	theme_base = st.get_option("theme.base")
	is_dark = theme_base == "dark"
	if is_dark:
		return {
			"template": "plotly_dark",
			"text": "#E5E7EB",
			"primary": "#7AA2F7",
			"secondary": "#8FB5FF",
			"accent": "#6FCF97",
			"muted": "#A3A3A3",
			"pie": ["#7AA2F7", "#8FB5FF", "#73C2BE", "#6FCF97", "#A3BE8C"],
			"heat": ["#22314A", "#476FA3", "#7AA2F7"],
		}
	return {
		"template": "plotly_white",
		"text": "#374151",
		"primary": "#1F3C88",
		"secondary": "#4E79A7",
		"accent": "#2E8B57",
		"muted": "#6B7280",
		"pie": ["#1F3C88", "#4E79A7", "#76B7B2", "#2E8B57", "#59A14F"],
		"heat": ["#DCE6F2", "#89A8D8", "#1F3C88"],
	}


def style_fig(fig, theme: dict):
	fig.update_layout(
		template=theme["template"],
		font={"color": theme["text"]},
		paper_bgcolor="rgba(0,0,0,0)",
		plot_bgcolor="rgba(0,0,0,0)",
		margin={"l": 20, "r": 20, "t": 55, "b": 20},
	)
	return fig


def main() -> None:
	st.title("Panel General de Ventas")
	st.caption("Retail de alimentos: conversiones, ventas, categorías y promociones")

	df = load_data()
	filtered_df = apply_filters(df)
	theme = get_theme_settings()

	if filtered_df.empty:
		st.warning("No hay datos con los filtros seleccionados.")
		st.stop()

	col_kpi1, col_kpi2, col_kpi3, col_gauge = st.columns([1, 1, 1, 1.25])
	col_kpi1.metric("Registros", f"{len(filtered_df):,}")
	col_kpi2.metric("Ventas totales", f"${filtered_df['total_sales'].sum():,.0f}")
	col_kpi3.metric("Conversion rate promedio", f"{filtered_df['conversion_rate'].mean() * 100:.2f}%")

	avg_conversion_pct = float(filtered_df["conversion_rate"].mean() * 100)
	gauge_max = max(40, round(max(avg_conversion_pct * 1.35, 32)))

	fig_gauge = go.Figure(
		go.Indicator(
			mode="gauge+number+delta",
			value=avg_conversion_pct,
			number={"suffix": "%", "font": {"size": 36, "color": theme["text"]}},
			delta={"reference": 30, "relative": False, "valueformat": ".2f", "suffix": " pp"},
			title={"text": "Conversión Promedio", "font": {"size": 18, "color": theme["text"]}},
			gauge={
				"axis": {"range": [0, gauge_max], "tickcolor": theme["muted"]},
				"bar": {"color": theme["primary"]},
				"bgcolor": "rgba(0,0,0,0)",
				"steps": [
					{"range": [0, 20], "color": "rgba(127,127,127,0.20)"},
					{"range": [20, 30], "color": "rgba(127,127,127,0.35)"},
					{"range": [30, gauge_max], "color": "rgba(127,127,127,0.15)"},
				],
				"threshold": {
					"line": {"color": theme["accent"], "width": 4},
					"thickness": 0.8,
					"value": 30,
				},
			},
		)
	)
	fig_gauge.update_layout(
		template=theme["template"],
		font={"color": theme["text"]},
		paper_bgcolor="rgba(0,0,0,0)",
		height=220,
		margin={"l": 8, "r": 8, "t": 30, "b": 8},
	)
	col_gauge.plotly_chart(fig_gauge, use_container_width=True)

	conv_by_day = (
		filtered_df.groupby("day_of_week", as_index=False)["conversion_rate"].mean().copy()
	)
	conv_by_day["day_of_week"] = pd.Categorical(
		conv_by_day["day_of_week"], categories=DAY_ORDER, ordered=True
	)
	conv_by_day = conv_by_day.sort_values("day_of_week")
	conv_by_day["conversion_pct"] = conv_by_day["conversion_rate"] * 100

	fig_conv_day = px.bar(
		conv_by_day,
		x="day_of_week",
		y="conversion_pct",
		color_discrete_sequence=[theme["primary"]],
		labels={"day_of_week": "Día de la semana", "conversion_pct": "Conversion rate (%)"},
		title="Conversión por Día",
	)
	fig_conv_day.update_traces(hovertemplate="Día: %{x}<br>Conversión: %{y:.2f}%<extra></extra>")
	st.plotly_chart(style_fig(fig_conv_day, theme), use_container_width=True)

	daily_sales = filtered_df.groupby("date", as_index=False)["total_sales"].sum()
	fig_sales = px.line(
		daily_sales,
		x="date",
		y="total_sales",
		color_discrete_sequence=[theme["secondary"]],
		markers=True,
		labels={"date": "Fecha", "total_sales": "Ventas diarias"},
		title="Ventas Diarias",
	)
	fig_sales.update_traces(hovertemplate="Fecha: %{x|%Y-%m-%d}<br>Ventas: $%{y:,.2f}<extra></extra>")
	st.plotly_chart(style_fig(fig_sales, theme), use_container_width=True)

	missing_cols = [col for col in CATEGORY_COLS if col not in filtered_df.columns]
	if missing_cols:
		st.error(f"Faltan columnas de categorías: {', '.join(missing_cols)}")
		st.stop()

	category_units = filtered_df[CATEGORY_COLS].sum().reset_index()
	category_units.columns = ["category", "units"]
	category_units["category"] = category_units["category"].str.replace("units_", "", regex=False)

	fig_pie = px.pie(
		category_units,
		names="category",
		values="units",
		hole=0.35,
		color="category",
		color_discrete_sequence=theme["pie"],
		title="Participación por Categoría",
	)
	fig_pie.update_traces(textposition="inside", textinfo="percent+label")
	st.plotly_chart(style_fig(fig_pie, theme), use_container_width=True)

	promo_traffic = (
		filtered_df.groupby("promo_type", as_index=False)["customer_traffic"].mean()
		.sort_values("customer_traffic", ascending=False)
	)

	fig_promo_bar = px.bar(
		promo_traffic,
		x="promo_type",
		y="customer_traffic",
		color="promo_type",
		color_discrete_sequence=theme["pie"],
		labels={"promo_type": "Tipo de descuento", "customer_traffic": "Clientes promedio"},
		title="Clientes Promedio por Descuento",
	)
	fig_promo_bar.update_traces(hovertemplate="Promo: %{x}<br>Clientes promedio: %{y:.1f}<extra></extra>")
	fig_promo_bar.update_layout(showlegend=False)
	st.plotly_chart(style_fig(fig_promo_bar, theme), use_container_width=True)

	meat_by_day = (
		filtered_df.groupby("day_of_week", as_index=False)["units_carnes"].mean().copy()
	)
	meat_by_day["day_of_week"] = pd.Categorical(
		meat_by_day["day_of_week"], categories=DAY_ORDER, ordered=True
	)
	meat_by_day = meat_by_day.sort_values("day_of_week")

	fig_meat_day = px.bar(
		meat_by_day,
		x="day_of_week",
		y="units_carnes",
		color_discrete_sequence=[theme["accent"]],
		labels={
			"day_of_week": "Día de la semana",
			"units_carnes": "Ventas de carne promedio (unidades)",
		},
		title="Ventas de Carne Promedio por Día",
	)
	fig_meat_day.update_traces(hovertemplate="Día: %{x}<br>Carne promedio: %{y:.1f}<extra></extra>")
	st.plotly_chart(style_fig(fig_meat_day, theme), use_container_width=True)

	monthly_sales = filtered_df.copy()
	monthly_sales["month_dt"] = monthly_sales["date"].dt.to_period("M").dt.to_timestamp()
	monthly_sales = monthly_sales.groupby("month_dt", as_index=False)["total_sales"].sum()
	monthly_sales["growth_pct"] = monthly_sales["total_sales"].pct_change() * 100
	monthly_sales = monthly_sales.dropna(subset=["growth_pct"])

	fig_growth = px.line(
		monthly_sales,
		x="month_dt",
		y="growth_pct",
		markers=True,
		color_discrete_sequence=[theme["primary"]],
		labels={"month_dt": "Mes", "growth_pct": "Crecimiento % vs período anterior"},
		title="Crecimiento Mensual vs Período Anterior",
	)
	fig_growth.update_traces(hovertemplate="Mes: %{x|%Y-%m}<br>Crecimiento: %{y:.2f}%<extra></extra>")
	fig_growth.add_hline(y=0, line_dash="dash", line_color=theme["muted"])
	st.plotly_chart(style_fig(fig_growth, theme), use_container_width=True)

	combined_monthly = filtered_df.copy()
	combined_monthly["month_dt"] = combined_monthly["date"].dt.to_period("M").dt.to_timestamp()
	combined_monthly = (
		combined_monthly.groupby("month_dt", as_index=False)
		.agg(customer_traffic=("customer_traffic", "mean"), conversion_rate=("conversion_rate", "mean"))
	)

	fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
	fig_combo.add_trace(
		go.Bar(
			x=combined_monthly["month_dt"],
			y=combined_monthly["customer_traffic"],
			name="Tráfico de clientes",
			marker_color=theme["secondary"],
			opacity=0.78,
			hovertemplate="Mes: %{x|%Y-%m}<br>Clientes: %{y:.1f}<extra></extra>",
		),
		secondary_y=False,
	)
	fig_combo.add_trace(
		go.Scatter(
			x=combined_monthly["month_dt"],
			y=combined_monthly["conversion_rate"],
			name="Conversion rate",
			mode="lines+markers",
			line={"color": theme["accent"], "width": 2.5},
			hovertemplate="Mes: %{x|%Y-%m}<br>Conversión: %{y:.3f}<extra></extra>",
		),
		secondary_y=True,
	)
	fig_combo.update_yaxes(title_text="Clientes", secondary_y=False)
	fig_combo.update_yaxes(title_text="Conversion rate", secondary_y=True)
	fig_combo.update_layout(title="Tráfico y Conversión Mensual", legend={"orientation": "h", "y": 1.08, "x": 0})
	st.plotly_chart(style_fig(fig_combo, theme), use_container_width=True)


if __name__ == "__main__":
	main()
