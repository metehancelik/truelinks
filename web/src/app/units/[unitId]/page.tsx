import { UnitView } from "./UnitView";

export default async function UnitPage({ params }: PageProps<"/units/[unitId]">) {
  const { unitId } = await params;
  return <UnitView unitId={unitId} />;
}
