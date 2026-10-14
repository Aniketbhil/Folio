import React from 'react'
import { Link } from 'react-router-dom'
import { PageContainer } from '../components/layout/PageContainer'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/Feedback'
import { AlertCircleIcon, HomeIcon } from '../components/ui/Icons'

export const NotFoundPage: React.FC = () => {
  return (
    <PageContainer>
      <div className="py-12">
        <EmptyState
          icon={<AlertCircleIcon className="w-6 h-6 text-amber-600" />}
          title="Page Not Found"
          description="The page you requested does not exist or has been moved."
          action={
            <Link to="/">
              <Button variant="primary" size="sm" leftIcon={<HomeIcon className="w-4 h-4" />}>
                Return to Workspace
              </Button>
            </Link>
          }
        />
      </div>
    </PageContainer>
  )
}
