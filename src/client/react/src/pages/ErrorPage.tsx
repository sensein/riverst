import { Button, Result, Typography } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'

export default function ErrorPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { message, status } = location.state || {}

  const defaultTitle = '404'
  const defaultSubTitle = 'Sorry, the page you visited does not exist.'

  const isCustom = !!message
  const resolvedStatus = status || (isCustom ? 'error' : '404')

  return (
    <div style={{ padding: '2rem' }}>
      <Result
        status={resolvedStatus}
        title={isCustom ? 'Oops!' : defaultTitle}
        subTitle={
          <Typography.Text style={{ fontSize: '18px' }}>
            {message || defaultSubTitle}
          </Typography.Text>
        }
        extra={
          <Button type="primary" onClick={() => navigate('/')}>
            Back Home
          </Button>
        }
      />
    </div>
  )
}
