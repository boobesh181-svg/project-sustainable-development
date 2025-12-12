import React from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { SupplierScatterPoint } from "../services/api";

interface SupplierRiskScatterProps {
  data: SupplierScatterPoint[];
}

export const SupplierRiskScatter: React.FC<SupplierRiskScatterProps> = ({ data }) => {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-medium text-slate-300 mb-4">Supplier Risk Analysis</h3>
      <ResponsiveContainer width="100%" height={200}>
        <ScatterChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
          <XAxis 
            dataKey="total_value" 
            name="Total Value"
            stroke="#94a3b8"
            fontSize={12}
            tickFormatter={(value) => `$${(value as number).toLocaleString()}`}
          />
          <YAxis 
            dataKey="project_count" 
            name="Project Count"
            stroke="#94a3b8"
            fontSize={12}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #475569",
              borderRadius: "8px",
            }}
            formatter={(value: any, name: string) => [
              name === "Total Value" ? `$${Number(value).toLocaleString()}` : value,
              name
            ]}
            labelFormatter={(value) => `Supplier: ${value}`}
          />
          <Scatter
            dataKey="project_count"
            fill="#f59e0b"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};
