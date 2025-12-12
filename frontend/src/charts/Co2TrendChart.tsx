import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { Co2TrendPoint } from "../services/api";

interface Props {
  data: Co2TrendPoint[];
}

export const Co2TrendChart: React.FC<Props> = ({ data }) => {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">
        12-month COf trend
      </h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} stackOffset="none">
            <XAxis dataKey="month" stroke="#64748b" tick={{ fontSize: 11 }} />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#020617",
                borderColor: "#1e293b",
                fontSize: 12,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area
              type="monotone"
              dataKey="embodied"
              stackId="1"
              stroke="#22c55e"
              fill="#22c55e33"
            />
            <Area
              type="monotone"
              dataKey="operational"
              stackId="1"
              stroke="#38bdf8"
              fill="#38bdf833"
            />
            <Area
              type="monotone"
              dataKey="saved"
              stackId="1"
              stroke="#f97316"
              fill="#f9731633"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
