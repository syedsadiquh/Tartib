import { redirect } from "next/navigation";

/** `/` is not a screen: the app opens on Today (ARCH §3.1). */
export default function RootPage() {
  redirect("/today");
}
