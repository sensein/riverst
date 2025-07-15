import { useEffect, useState } from 'react';
import {
  Form,
  Input,
  Select,
  Switch,
  Button,
  Typography,
  Checkbox,
  Tooltip
} from 'antd';
import { InfoCircleOutlined, CloseOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import validator from '@rjsf/validator-ajv8';
import { usePipecatClientTransportState } from '@pipecat-ai/client-react';
import axios from 'axios';
import { getUserId } from '../utils/userId';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

const SettingsForm = ({ schema, onSubmit }) => {
  const transportState = usePipecatClientTransportState();
  const [form] = Form.useForm();
  const [isValid, setIsValid] = useState(false);
  const [dynamicEnums, setDynamicEnums] = useState({ books: [] });
  const [userId, setUserId] = useState<string | null>(null);

  const options = schema?.properties?.options?.properties || {};
  const requiredFields = schema?.properties?.options?.required || [];

  const schemaName = schema?.properties?.name?.const;
  const schemaDescription = schema?.properties?.description?.const;

  const pipelineModality = Form.useWatch(['options', 'pipeline_modality'], form);

  useEffect(() => {
    const fetchUserId = async () => {
      const id = await getUserId();
      setUserId(id);
      form.setFieldsValue({ user_id: id });
    };

    fetchUserId();

    const fetchBooks = async () => {
      try {
        const response = await axios.get('http://localhost:7860/books');
        setDynamicEnums(prev => ({
          ...prev,
          books: response.data
        }));
      } catch (error) {
        console.error('Failed to fetch books:', error);
      }
    };

    fetchBooks();
    validateSchema();
  }, []);

  useEffect(() => {
    if (!pipelineModality) return;

    const currentValues = form.getFieldValue('options') || {};
    const updates = { ...currentValues };

    if (pipelineModality === 'classic') {
      updates.llm_type = 'openai';
      updates.stt_type = 'openai';
      updates.tts_type = 'kokoro';
    } else if (pipelineModality === 'e2e') {
      updates.llm_type = 'gemini';
      updates.stt_type = undefined;
      updates.tts_type = 'kokoro';
    }

    form.setFieldsValue({ options: updates });
  }, [pipelineModality]);

  const validateSchema = async () => {
    const values = await form.getFieldsValue(true);
    const result = validator.validateFormData(schema, values);
    setIsValid(result.errors.length === 0);
  };

  const renderLabel = (label, description) => (
    <span>
      {label}
      {description && (
        <Tooltip title={description}>
          <InfoCircleOutlined style={{ marginLeft: 8, color: '#999' }} />
        </Tooltip>
      )}
    </span>
  );

  const renderFormItem = (key, config) => {
    if (config.const !== undefined) return null;
    if (['stt_type'].includes(key) && pipelineModality !== 'classic') return null;
    if (key === 'llm_type') {
      const filteredEnums =
        pipelineModality === 'classic'
          ? ['openai', 'llama3.2']
          : ['openai_realtime_beta', 'gemini'];
      config.enum = filteredEnums;
    }

    const rules = [];
    if (requiredFields.includes(key)) rules.push({ required: true, message: `${key} is required` });
    if (config.maxLength) rules.push({ max: config.maxLength });

    const label = (config.title || key.replace(/_/g, ' ')).toUpperCase();
    const namePath = ['options', key];
    const labelWithTooltip = renderLabel(label, config.description);

    if (config.type === 'array' && config.items?.enum) {
      if (config.minItems) {
        rules.push({
          validator: (_, value) => {
            if (Array.isArray(value) && value.length < config.minItems) {
              return Promise.reject(new Error(`Please select at least ${config.minItems} item(s).`));
            }
            return Promise.resolve();
          },
        });
      }
      return (
        <Form.Item key={key} name={namePath} label={labelWithTooltip} rules={rules}>
          <Checkbox.Group options={config.items.enum} />
        </Form.Item>
      );
    }

    if ((config.enum || config.dynamicEnum) && config.type !== 'array') {
      if (config.dynamicEnum === 'books') {
        return (
          <Form.Item key={key} name={namePath} label={labelWithTooltip} rules={rules}>
            <Select>
              {dynamicEnums.books.map((book) => (
                <Select.Option key={book.id} value={book.path}>
                  {book.title}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        );
      }

      return (
        <Form.Item key={key} name={namePath} label={labelWithTooltip} rules={rules}>
          <Select>
            {config.enum.map((val) => (
              <Select.Option key={val} value={val}>
                {val}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
      );
    }

    switch (config.type) {
      case 'boolean':
        return (
          <Form.Item
            key={key}
            name={namePath}
            label={labelWithTooltip}
            valuePropName="checked"
            rules={rules}
          >
            <Switch />
          </Form.Item>
        );
      case 'string':
        const multiline = config.maxLength && config.maxLength > 100;
        return (
          <Form.Item key={key} name={namePath} label={labelWithTooltip} rules={rules}>
            {multiline ? <TextArea autoSize /> : <Input />}
          </Form.Item>
        );
      default:
        return null;
    }
  };

  const defaultOptions = Object.entries(options).reduce((acc, [key, def]) => {
    acc[key] =
      def.default ??
      (def.type === 'boolean' ? false : def.type === 'array' ? [] : '');
    return acc;
  }, {});

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 24, position: 'relative' }}>
      <Link to="/" style={{ position: 'absolute', top: 12, right: 12 }}>
        <Button type="text" icon={<CloseOutlined />} />
      </Link>

      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ marginBottom: 4 }}>{schemaName}</Title>
        <Paragraph type="secondary" style={{ margin: 0 }}>{schemaDescription}</Paragraph>
      </div>

      <Form
        form={form}
        layout="vertical"
        initialValues={{ options: defaultOptions }}
        onFinish={({ options, user_id }) => onSubmit({ ...options, user_id })}
        onFieldsChange={validateSchema}
      >
        <Form.Item
          name="user_id"
          label="USER ID"
          rules={[{ required: true, message: 'User ID is required' }]}
        >
          <Input />
        </Form.Item>

        {Object.entries(options).map(([key, config]) =>
          renderFormItem(key, config)
        )}

        <Form.Item>
          <Button
            type="primary"
            disabled={!isValid || transportState === 'connecting'}
            loading={transportState === 'connecting'}
            onClick={async () => {
              const values = await form.getFieldsValue(true);
              const result = validator.validateFormData(schema, values);
              if (result.errors.length > 0) return;
              onSubmit({ ...values.options, user_id: values.user_id });
            }}
          >
            Confirm session settings
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default SettingsForm;
