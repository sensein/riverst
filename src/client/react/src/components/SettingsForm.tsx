/**
 * SettingsForm.tsx
 * Renders a form based on a JSON schema.
 * - Handles form validation and submission.
 * - Renders form inputs based on the schema.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import validator from '@rjsf/validator-ajv8';
import { JSONSchema7, JSONSchema7Definition } from 'json-schema';

import {
  Form,
  Input,
  Select,
  Switch,
  Button,
  Typography,
  Checkbox,
  Tooltip,
} from 'antd';
import { InfoCircleOutlined, CloseOutlined } from '@ant-design/icons';

import { usePipecatClientTransportState } from '@pipecat-ai/client-react';
import { getRandomUserId } from '../utils/userId';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

// Props
interface SettingsFormProps {
  schema: JSONSchema7;
  onSubmit: (data: any) => void;
}

const SettingsForm: React.FC<SettingsFormProps> = ({ schema, onSubmit }) => {
  const [form] = Form.useForm();
  const transportState = usePipecatClientTransportState();
  const [isValid, setIsValid] = useState(false);
  const [dynamicEnums, setDynamicEnums] = useState<{ books: { id: string; path: string; title: string }[] }>({ books: [] });

  // Extract activity name from schema
  const activityName = (schema?.properties as any)?.name?.const;
  const [maxIndices, setMaxIndices] = useState<number | null>(null);
  const [indexType, setIndexType] = useState<string>('chapters');

  // Defaults extracted from schema
  const defaultAnimations =
    (schema.properties?.options as any)?.properties?.body_animations?.default ?? [];
  const defaultCamera =
    (schema.properties?.options as any)?.properties?.camera_settings?.default ?? 'upper';

  const isObjectSchema = (def: JSONSchema7Definition | undefined): def is JSONSchema7 =>
    typeof def === 'object' && def !== null;

  const options =
    isObjectSchema(schema?.properties?.options) && 'properties' in schema.properties.options
      ? schema.properties.options.properties || {}
      : {};

  const requiredFields =
    isObjectSchema(schema?.properties?.options) && 'required' in schema.properties.options
      ? schema.properties.options.required || []
      : [];

  const schemaName =
    isObjectSchema(schema?.properties?.name) && 'const' in schema.properties.name
      ? schema.properties.name.const
      : '';

  const schemaDescription =
    isObjectSchema(schema?.properties?.description) && 'const' in schema.properties.description
      ? schema.properties.description.const
      : '';

  const pipelineModality = Form.useWatch(['options', 'pipeline_modality'], form);
  const embodiment = Form.useWatch(['options', 'embodiment'], form);
  const selectedBook = Form.useWatch(['options', 'activity_variables_path'], form);

  // Schema validator
  const validateSchema = useCallback(async () => {
    const values = await form.getFieldsValue(true);
    const result = validator.validateFormData(schema, values);
    setIsValid(result.errors.length === 0);
  }, [form, schema]);

  // Fetch user ID and dynamic enum options
  useEffect(() => {
    form.setFieldsValue({ user_id: getRandomUserId() });

    const fetchBooks = async () => {
      try {
        if (activityName) {
          const response = await axios.get('/api/resources', {
            params: { activity: activityName }
          });
          setDynamicEnums(prev => ({ ...prev, books: response.data }));
        } else {
          // Fallback to generic resources if no activity name
          const response = await axios.get('/api/resources');
          setDynamicEnums(prev => ({ ...prev, books: response.data }));
        }
      } catch (error) {
        console.error('Failed to fetch books:', error);
      }
    };

    fetchBooks();
    validateSchema();
  }, [form, validateSchema, activityName]);

  // Fetch index count when book selection changes
  useEffect(() => {
    if (!selectedBook) {
      setMaxIndices(null);
      setIndexType('chapters');
      return;
    }

    const fetchResourceIndices = async () => {
      try {
        const response = await axios.get('/api/resources/indices', {
          params: { resourcePath: selectedBook }
        });
        setMaxIndices(response.data.maxIndices);
        setIndexType(response.data.indexType || 'chapters');
      } catch (error) {
        console.error('Failed to fetch resource indices:', error);
        setMaxIndices(null);
        setIndexType('chapters');
      }
    };

    fetchResourceIndices();
  }, [selectedBook]);

  // Update field values based on pipeline modality
  useEffect(() => {
    if (!pipelineModality) return;

    const optionsSchema = (schema.properties?.options as JSONSchema7)?.properties || {};
    const getDefault = (key: string) => (optionsSchema[key] as any)?.default;

    const currentValues = form.getFieldValue('options') || {};
    const updates = { ...currentValues };

    if (pipelineModality === 'classic') {
      updates.llm_type = getDefault('llm_type');
      updates.stt_type = getDefault('stt_type');
      updates.tts_type = getDefault('tts_type');
    } else if (pipelineModality === 'e2e') {
      updates.llm_type = 'openai_gpt-realtime';
      updates.stt_type = undefined;
      updates.tts_type = undefined;
    }

    form.setFieldsValue({ options: updates });
  }, [pipelineModality, form, schema]);

  // Revalidate schema on embodiment change
  useEffect(() => {
    validateSchema();
  }, [validateSchema, embodiment]);

  // Update dependent animation/camera fields
  useEffect(() => {
    const currentOptions = form.getFieldValue('options') || {};
    form.setFieldsValue({
      options: {
        ...currentOptions,
        body_animations: embodiment === 'humanoid_avatar' ? defaultAnimations : [],
        camera_settings: embodiment === 'humanoid_avatar' ? defaultCamera : undefined,
      },
    });
  }, [embodiment, form]);

  // Label with optional tooltip
  const renderLabel = (label: string, description?: string) => (
    <span>
      {label}
      {description && (
        <Tooltip title={description}>
          <InfoCircleOutlined style={{ marginLeft: 8, color: '#999' }} />
        </Tooltip>
      )}
    </span>
  );

  // Render form input based on config
  const renderFormItem = (key: string, config: any) => {
    if (config.const !== undefined) return null;
    if (
      ['body_animations', 'camera_settings'].includes(key) &&
      form.getFieldValue(['options', 'embodiment']) !== 'humanoid_avatar'
    ) {
      return null;
    }
    if (['stt_type', 'tts_type'].includes(key) && pipelineModality !== 'classic') return null;

    if (key === 'llm_type') {
      config.enum = pipelineModality === 'classic'
        ? ['openai', 'ollama/qwen3:4b-instruct-2507-q4_K_M']
        : ['openai_gpt-realtime'];
    }

    const rules = [];
    if (requiredFields.includes(key)) rules.push({ required: true, message: `${key} is required` });
    if (config.maxLength) rules.push({ max: config.maxLength });

    const label = (config.title || key.replace(/_/g, ' ')).toUpperCase();
    const namePath = ['options', key];
    const labelWithTooltip = renderLabel(label, config.description);

    // Enum list (array of checkboxes)
    if (config.type === 'array' && config.items?.enum) {
      if (config.minItems) {
        rules.push({
          validator: (_: any, value: any) =>
            Array.isArray(value) && value.length < config.minItems
              ? Promise.reject(new Error(`Please select at least ${config.minItems} item(s).`))
              : Promise.resolve(),
        });
      }
      return (
        <Form.Item key={key} name={namePath} label={labelWithTooltip} rules={rules}>
          <Checkbox.Group options={config.items.enum} />
        </Form.Item>
      );
    }

    // Enum select (from schema or API)
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
            {config.enum.map((val: string) => (
              <Select.Option key={val} value={val}>
                {val}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
      );
    }

    // Boolean field
    if (config.type === 'boolean') {
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
    }


    // String (text or textarea)
    if (config.type === 'string') {
      const multiline = config.maxLength && config.maxLength > 100;
      return (
        <Form.Item key={key} name={namePath} label={labelWithTooltip} rules={rules}>
          {multiline ? <TextArea autoSize /> : <Input />}
        </Form.Item>
      );
    }


    // Integer or nullable integer field
    if (config.type === 'integer' || (Array.isArray(config.type) && config.type.includes('integer'))) {
      const max = key === 'index' && maxIndices ? maxIndices : config.maximum;

      // Add validation rules for resource index
      if (key === 'index' && maxIndices) {
        const indexTypeSingular = indexType.slice(-1) === 's' ? indexType.slice(0, -1) : indexType;
        rules.push({
          validator: (_: any, value: any) => {
            if (value === undefined || value === null || value === '') {
              return Promise.resolve();
            }
            const numValue = Number(value);
            if (isNaN(numValue)) {
              return Promise.reject(new Error('Please enter a valid number'));
            }
            if (!Number.isInteger(numValue)) {
              return Promise.reject(new Error(`${indexTypeSingular} must be a whole number`));
            }
            if (numValue < 1) {
              return Promise.reject(new Error(`${indexTypeSingular} must be at least 1`));
            }
            if (numValue > maxIndices) {
              return Promise.reject(new Error(`${indexTypeSingular} must be no more than ${maxIndices}`));
            }
            return Promise.resolve();
          }
        });
      }

      return (
        <Form.Item key={key} name={namePath} label={labelWithTooltip} rules={rules}>
          <Input
            type="number"
            min={config.minimum}
            max={max}
            placeholder={key === 'index' && maxIndices ? `1-${maxIndices}` : undefined}
          />
        </Form.Item>
      );
    }

    return null;
  };

  // Extract default values from schema
  const defaultOptions = Object.entries(options).reduce<Record<string, any>>((acc, [key, def]) => {
    if (typeof def !== 'object' || def === null) return acc;
    acc[key] =
      'default' in def ? (def as any).default :
      (def as any).type === 'boolean' ? false :
      (def as any).type === 'array' ? [] : '';
    return acc;
  }, {});

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 24, position: 'relative' }}>
      <Link to="/" style={{ position: 'absolute', top: 12, right: 12 }}>
        <Button type="text" icon={<CloseOutlined />} />
      </Link>

      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ marginBottom: 4 }}>{String(schemaName)}</Title>
        <Paragraph type="secondary" style={{ margin: 0 }}>{String(schemaDescription)}</Paragraph>
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

        {Object.entries(options).map(([key, config]) => renderFormItem(key, config))}

        <Form.Item>
          <Button
            type="primary"
            disabled={!isValid || transportState === 'connecting'}
            loading={transportState === 'connecting'}
            onClick={async () => {
              const values = await form.getFieldsValue(true);
              const result = validator.validateFormData(schema, values);
              if (result.errors.length === 0) {
                onSubmit({ ...values.options, user_id: values.user_id });
              }
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
