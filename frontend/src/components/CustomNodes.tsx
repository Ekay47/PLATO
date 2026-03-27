import { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import './Nodes.css';

const HandleStyle = { width: 8, height: 8, background: '#555' };
// Smaller handle for merge nodes to avoid visual clutter
const SmallHandleStyle = { width: 4, height: 4, background: '#555', opacity: 0 }; 

export const StartNode = memo(({ isConnectable }: NodeProps) => {
  return (
    <div className="plantuml-node start">
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
        style={HandleStyle}
      />
    </div>
  );
});

export const StopNode = memo(({ isConnectable }: NodeProps) => {
  return (
    <div className="plantuml-node stop">
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
        style={HandleStyle}
      />
    </div>
  );
});

export const ActivityNode = memo(({ data, isConnectable }: NodeProps) => {
  return (
    <div className="plantuml-node activity">
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
        style={HandleStyle}
      />
      <div>{data.label}</div>
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
        style={HandleStyle}
      />
    </div>
  );
});

export const ConditionNode = memo(({ data, isConnectable }: NodeProps) => {
  return (
    <div className="uml-diamond-wrapper">
      <div className="uml-diamond-shape">
        <div className="uml-diamond-content">
          {data.label || "?"}
        </div>
      </div>
      
      {/* Top Input */}
      <Handle
        type="target"
        position={Position.Top}
        className="uml-handle"
        isConnectable={isConnectable}
        style={{ top: 0, background: '#555' }}
      />
      
      {/* Bottom Output (Yes/Primary) */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="yes"
        className="uml-handle"
        isConnectable={isConnectable}
        style={{ bottom: 0, background: '#555' }}
      />
      
      {/* Right Output (No/Secondary) */}
      <Handle
        type="source"
        position={Position.Right}
        id="no"
        className="uml-handle"
        isConnectable={isConnectable}
        style={{ right: 0, background: '#555' }}
      />
      
      {/* Left Output (Optional) */}
       <Handle
        type="source"
        position={Position.Left}
        id="left"
        className="uml-handle"
        isConnectable={isConnectable}
        style={{ left: 0, background: '#555' }}
      />
    </div>
  );
});

export const ForkNode = memo(({ isConnectable }: NodeProps) => {
  return (
    <div className="plantuml-node fork">
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
        style={{ ...HandleStyle, opacity: 0 }} // Hidden handle for clean look
      />
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
        style={{ ...HandleStyle, opacity: 0 }}
      />
    </div>
  );
});

export const MergeNode = memo(({ isConnectable }: NodeProps) => {
    return (
      <div className="plantuml-node merge">
        <Handle
          type="target"
          position={Position.Top}
          isConnectable={isConnectable}
          style={SmallHandleStyle}
        />
        <Handle
          type="source"
          position={Position.Bottom}
          isConnectable={isConnectable}
          style={SmallHandleStyle}
        />
      </div>
    );
  });

export const NoteNode = memo(({ data }: NodeProps) => {
  return (
    <div className="plantuml-node note">
      <div>{data.label}</div>
    </div>
  );
});

export const nodeTypes = {
  start: StartNode,
  stop: StopNode,
  activity: ActivityNode,
  condition: ConditionNode,
  fork: ForkNode,
  join: ForkNode, 
  merge: MergeNode,
  note: NoteNode,
  // Mapping for group/composite
  group: ActivityNode, 
};
