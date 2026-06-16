import { ConfiguratorShell } from './components/shell/ConfiguratorShell'
import { useConfiguratorState } from './state/useConfiguratorState'

function App() {
  const {
    activeModule,
    activeConfig,
    setActiveModule,
    setTitle,
    setLocationQuery,
    setTemplateId,
    setPaletteId,
    toggleObject,
    previewViewport,
    previewObjects,
    selectedObjectId,
    placementType,
    setPlacementType,
    setPreviewViewport,
    resetPreviewViewport,
    addObjectAtPoint,
    moveObject,
    selectObject,
    deleteObject,
    deleteSelectedObject,
  } = useConfiguratorState()

  return (
    <ConfiguratorShell
      activeModule={activeModule}
      activeConfig={activeConfig}
      onModuleChange={setActiveModule}
      onTitleChange={setTitle}
      onLocationChange={setLocationQuery}
      onTemplateChange={setTemplateId}
      onPaletteChange={setPaletteId}
      onObjectToggle={toggleObject}
      previewViewport={previewViewport}
      previewObjects={previewObjects}
      selectedObjectId={selectedObjectId}
      placementType={placementType}
      onPlacementTypeChange={setPlacementType}
      onPreviewViewportChange={setPreviewViewport}
      onPreviewViewportReset={resetPreviewViewport}
      onAddPreviewObject={addObjectAtPoint}
      onMovePreviewObject={moveObject}
      onSelectPreviewObject={selectObject}
      onDeletePreviewObject={deleteObject}
      onDeleteSelectedPreviewObject={deleteSelectedObject}
    />
  )
}

export default App
