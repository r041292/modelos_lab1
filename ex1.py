from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Dashboard Retail Alimentos", layout="wide")

PALETTE = {
	"primary": "#1F3C88",
	"secondary": "#4E79A7",
	"accent": "#2E8B57",
	"neutral": "#4A4A4A",
	"bg_soft": "#F5F7FA",
}

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


def style_fig(fig):
	fig.update_layout(
		template="plotly_white",
		font={"color": PALETTE["neutral"]},
		paper_bgcolor="white",
		plot_bgcolor="white",
		margin={"l": 20, "r": 20, "t": 55, "b": 20},
	)
	return fig


def main() -> None:
	st.markdown(
		"""
		<style>
		.main { background-color: #F8FAFC; }
		.block-container { padding-top: 1.4rem; padding-bottom: 1.2rem; }
		h1, h2, h3 { color: #1F3C88; }
		</style>
		""",
		unsafe_allow_html=True,
	)

	st.title("Panel General de Ventas")
	st.caption("Retail de alimentos: conversiones, ventas, categorías y promociones")

	df = load_data()
	filtered_df = apply_filters(df)

	if filtered_df.empty:
		st.warning("No hay datos con los filtros seleccionados.")
		st.stop()

	col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
	col_kpi1.metric("Registros", f"{len(filtered_df):,}")
	col_kpi2.metric("Ventas totales", f"${filtered_df['total_sales'].sum():,.0f}")
	col_kpi3.metric("Conversion rate promedio", f"{filtered_df['conversion_rate'].mean() * 100:.2f}%")

	conv_by_day = (
		filtered_df.groupby("day_of_week", as_index=False)["conversion_rate"].mean().copy()
	)
	conv_by_day["day_of_week"] = pd.Categorical(conv_by_day["day_of_week"], categories=DAY_ORDER, ordered=True)
	conv_by_day = conv_by_day.sort_values("day_of_week")
	conv_by_day["conversion_pct"] = conv_by_day["conversion_rate"] * 100

	fig_conv = px.bar(
		conv_by_day,
		x="day_of_week",
		y="conversion_pct",
		color_discrete_sequence=[PALETTE["primary"]],
		labels={"day_of_week": "Día de la semana", "conversion_pct": "Conversion rate (%)"},
		title="Conversión por Día",
	)
	fig_conv.update_traces(hovertemplate="Día: %{x}<br>Conversion: %{y:.2f}%<extra></extra>")
	st.plotly_chart(style_fig(fig_conv), use_container_width=True)

	daily_sales = filtered_df.groupby("date", as_index=False)["total_sales"].sum()
	fig_sales = px.line(
		daily_sales,
		x="date",
		y="total_sales",
		color_discrete_sequence=[PALETTE["secondary"]],
		markers=True,
		labels={"date": "Fecha", "total_sales": "Ventas diarias"},
		title="Ventas Diarias",
	)
	fig_sales.update_traces(hovertemplate="Fecha: %{x|%Y-%m-%d}<br>Ventas: $%{y:,.2f}<extra></extra>")
	st.plotly_chart(style_fig(fig_sales), use_container_width=True)

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
		color_discrete_sequence=[
			PALETTE["primary"],
			PALETTE["secondary"],
			"#76B7B2",
			PALETTE["accent"],
			"#59A14F",
		],
		title="Participación por Categoría",
	)
	fig_pie.update_traces(textposition="inside", textinfo="percent+label")
	st.plotly_chart(style_fig(fig_pie), use_container_width=True)

	heat_df = filtered_df.copy()
	heat_df["traffic_bin"] = pd.cut(
		heat_df["customer_traffic"],
		bins=8,
		include_lowest=True,
	).astype(str)

	heat_data = (
		heat_df.groupby(["promo_type", "traffic_bin"], as_index=False)
		.size()
		.rename(columns={"size": "count_days"})
	)

	fig_heat = px.density_heatmap(
		heat_data,
		x="promo_type",
		y="traffic_bin",
		z="count_days",
		color_continuous_scale=["#DCE6F2", "#89A8D8", PALETTE["primary"]],
		labels={
			"promo_type": "Tipo de promoción",
			"traffic_bin": "Rango de customer_traffic",
			"count_days": "Número de días",
		},
		title="Promoción vs Tráfico",
	)
	st.plotly_chart(style_fig(fig_heat), use_container_width=True)


if __name__ == "__main__":
	main()
