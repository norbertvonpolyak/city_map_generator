import { ConfiguratorShell } from './components/shell/ConfiguratorShell'
import { useConfiguratorState } from './state/useConfiguratorState'

function App() {
  const {
    activeModule,
    activeConfig,
    setActiveModule,
    setTitle,
    setSelectedLocation,
    setLocationCoordinates,
    generateCityPreview,
    setTemplateId,
    setPaletteId,
    setTypographyStyle,
    setStarDateIso,
    setStarSkyStyle,
    toggleObject,
    previewViewport,
    previewObjects,
    selectedObjectId,
    placementType,
    cityPreviewSvg,
    cityPreviewStatus,
    cityPreviewError,
    hasUserSelectedCityLocation,
    setPlacementType,
    setPreviewViewport,
    resetPreviewViewport,
    addObjectAtPoint,
    moveObject,
    selectObject,
    deleteObject,
    deleteSelectedObject,
    printSizeId,
    setPrintSizeId,
  } = useConfiguratorState()

  return (
    <ConfiguratorShell
      activeModule={activeModule}
      activeConfig={activeConfig}
      onModuleChange={setActiveModule}
      onTitleChange={setTitle}
      onLocationSelect={setSelectedLocation}
      onLocationCenterChange={setLocationCoordinates}
      onGenerateCityPreview={generateCityPreview}
      onTemplateChange={setTemplateId}
      onPaletteChange={setPaletteId}
      onTypographyStyleChange={setTypographyStyle}
      onStarDateChange={setStarDateIso}
      onStarSkyStyleChange={setStarSkyStyle}
      onObjectToggle={toggleObject}
      previewViewport={previewViewport}
      previewObjects={previewObjects}
      selectedObjectId={selectedObjectId}
      placementType={placementType}
      cityPreviewSvg={cityPreviewSvg}
      cityPreviewStatus={cityPreviewStatus}
      cityPreviewError={cityPreviewError}
      hasUserSelectedCityLocation={hasUserSelectedCityLocation}
      onPlacementTypeChange={setPlacementType}
      onPreviewViewportChange={setPreviewViewport}
      onPreviewViewportReset={resetPreviewViewport}
      onAddPreviewObject={addObjectAtPoint}
      onMovePreviewObject={moveObject}
      onSelectPreviewObject={selectObject}
      onDeletePreviewObject={deleteObject}
      onDeleteSelectedPreviewObject={deleteSelectedObject}
      printSizeId={printSizeId}
      onPrintSizeChange={setPrintSizeId}
    />
  )
}

export default App
