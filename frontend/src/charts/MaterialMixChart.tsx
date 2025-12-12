import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import type { MaterialMixSlice } from "../services/api";

interface Props {
  data: MaterialMixSlice[];
}

const COLORS = ["#22c55e", "#38bdf8", "#f97316", "#a855f7", "#e11d48", "#facc15"];

export const MaterialMixChart: React.FC<Props> = ({ data }) => {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Material mix</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="qty"
              nameKey="material_type"
              cx="50%"
              cy="50%"
              outerRadius={80}
              label={(entry) => entry.material_type}
            >
              {data.map((entry, index) => (
                <Cell key={entry.material_type} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: "#020617",
                borderColor: "#1e293b",
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
