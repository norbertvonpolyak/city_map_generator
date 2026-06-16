import { ConfiguratorShell } from './components/shell/ConfiguratorShell'
import { useConfiguratorState } from './state/useConfiguratorState'

function App() {
  const {
    activeModule,
    activeConfig,
    setActiveModule,
    setTitle,
    setLocationQuery,
    generateCityPreview,
    setTemplateId,
    setPaletteId,
    toggleObject,
    previewViewport,
    previewObjects,
    selectedObjectId,
    placementType,
    cityPreviewSvg,
    cityPreviewStatus,
    cityPreviewError,
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
      onGenerateCityPreview={generateCityPreview}
      onTemplateChange={setTemplateId}
      onPaletteChange={setPaletteId}
      onObjectToggle={toggleObject}
      previewViewport={previewViewport}
      previewObjects={previewObjects}
      selectedObjectId={selectedObjectId}
      placementType={placementType}
      cityPreviewSvg={cityPreviewSvg}
      cityPreviewStatus={cityPreviewStatus}
      cityPreviewError={cityPreviewError}
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
