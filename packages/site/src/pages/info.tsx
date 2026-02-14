import PageLayout from '@components/page_layout'
import { useIsMobile } from '@/hooks/use-mobile'
import AddHistoryEventDialog from '@components/history_event_add_dialog'
import HistoryEventsDataTable from '@components/history_events_data_table'

const InfoPage = () => {
  const isMobile = useIsMobile()

  return (
    <>
      <PageLayout>
        <div className="flex items-center justify-between px-2 md:px-0 mb-4">
          <div className="text-xl md:text-2xl font-bold">历史事件管理</div>
          <AddHistoryEventDialog />
        </div>

        <div className={`w-full ${isMobile ? 'px-2' : ''}`}>
          <HistoryEventsDataTable />
        </div>
      </PageLayout>
    </>
  )
}

export default InfoPage

