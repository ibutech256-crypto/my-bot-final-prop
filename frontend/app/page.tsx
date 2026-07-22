"use client";

import dynamic from "next/dynamic";
import React from "react";

const ClientDashboard = dynamic(() => import("./ClientDashboard"), { ssr: false });

export default function Page() {
  return <ClientDashboard />;
}
